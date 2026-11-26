import { useCallback, useEffect, useRef } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { useNoticeQueue } from "@/components/custom/notice/use-notice-queue";
import { api, ApiError } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import { useListSort, useSettledSort } from "@/lib/use-list-sort";
import {
  FINDING_SORT_KEYS,
  PAGE_SIZE,
  isKind,
  isStatus,
  runSummary,
  runTone,
  type Finding,
  type KindFilter,
  type StatusFilter,
} from "../logic/reconcile-view";

type FindingsPage = components["schemas"]["ReconcileFindingsPage"];

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : "操作失败，请重试";
}

/** 对账页：筛选与排序在 URL 里；触发后靠 SSE + 轮询刷新同一个查询，结果发到右下角提示。 */
export function useReconcile() {
  const { shopIds } = useShopFilter();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const sorting = useListSort(FINDING_SORT_KEYS);
  const { notices, notify, dismissNotice } = useNoticeQueue();

  const kindParam = params.get("kind");
  const kind: KindFilter = isKind(kindParam) ? kindParam : "all";
  const statusParam = params.get("status");
  const status: StatusFilter = isStatus(statusParam) ? statusParam : "all";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const update = useCallback(
    (changes: Record<string, string | null>) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      });
    },
    [setParams],
  );

  const setKind = (value: KindFilter) =>
    update({ kind: value === "all" ? null : value, page: null });
  const setStatus = (value: StatusFilter) =>
    update({ status: value === "all" ? null : value, page: null });
  const setPage = (value: number) =>
    update({ page: value > 1 ? String(value) : null });

  const query = useQuery({
    queryKey: queryKeys.reconcileFindings(shopIds, { kind, status, page, ...sorting.query }),
    queryFn: () =>
      api.get<FindingsPage>("/api/reconcile/findings", {
        shop_ids: shopIds,
        kind: kind === "all" ? undefined : kind,
        status: status === "all" ? undefined : status,
        page,
        page_size: PAGE_SIZE,
        ...sorting.query,
      }),
    placeholderData: keepPreviousData,
    refetchInterval: (q) =>
      q.state.data?.run?.status === "running" ? 3000 : false,
  });

  const runMutation = useMutation({
    mutationFn: () =>
      api.post<components["schemas"]["ReconcileStarted"]>("/api/reconcile/run", {
        window_days: 30,
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.reconcileRoot() });
    },
    onError: (e) => notify("reconcile:run", "danger", message(e)),
  });

  const markMutation = useMutation({
    mutationFn: (findingId: number) =>
      api.patch<Finding>(`/api/reconcile/findings/${findingId}`, { status: "handled" }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.reconcileRoot() });
    },
    onError: (e) => notify("reconcile:mark", "danger", message(e)),
  });

  // 本页触发的批次跑完后报一次结果
  const startedRunId = runMutation.data?.run_id;
  const latestRun = query.data?.run ?? null;
  const reportedRunId = useRef<string | null>(null);
  useEffect(() => {
    if (!latestRun || latestRun.status === "running") return;
    if (latestRun.run_id !== startedRunId || reportedRunId.current === latestRun.run_id) return;
    reportedRunId.current = latestRun.run_id;
    notify("reconcile:run", runTone(latestRun), runSummary(latestRun));
  }, [latestRun, startedRunId, notify]);

  useEventSubscription("reconcile_done", () => {
    void client.invalidateQueries({ queryKey: queryKeys.reconcileRoot() });
  });

  const shownSort = useSettledSort(sorting.sort, !query.isPlaceholderData);
  return {
    query,
    rows: query.data?.items ?? [],
    run: latestRun,
    kind,
    status,
    page,
    sort: shownSort,
    setSort: sorting.setSort,
    setKind,
    setStatus,
    setPage,
    runNow: () => runMutation.mutate(),
    running: runMutation.isPending || query.data?.run?.status === "running",
    markHandled: markMutation.mutate,
    marking: markMutation.isPending,
    notices,
    dismissNotice,
  };
}

export type ReconcileState = ReturnType<typeof useReconcile>;

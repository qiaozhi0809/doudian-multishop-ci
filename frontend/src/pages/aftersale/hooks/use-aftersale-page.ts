import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { metricQueries } from "@/lib/metric-queries";
import { queryKeys } from "@/lib/query-keys";
import { useShops } from "@/lib/use-shops";
import { PAGE_SIZE, isView, parseStatus, type View } from "../logic/aftersale-page";
import { useAftersaleSync } from "./use-aftersale-sync";

type PageData = components["schemas"]["AftersalePage"];
type StatusesResponse = components["schemas"]["AftersaleStatusesResponse"];

/** 售后页的全部数据：视图（待办 / 全部）、状态筛选、页码都在 URL 里。 */
export function useAftersalePage() {
  const shops = useShops();
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();

  const rawView = params.get("view");
  const view: View = isView(rawView) ? rawView : "todo";
  const status = view === "all" ? parseStatus(params.get("status")) : undefined;
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const update = useCallback(
    (patch: { view?: View; page?: number }) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (patch.view !== undefined) {
          if (patch.view === "todo") next.delete("view");
          else next.set("view", patch.view);
          next.delete("status");
          next.delete("page");
        }
        if (patch.page !== undefined) {
          if (patch.page > 1) next.set("page", String(patch.page));
          else next.delete("page");
        }
        return next;
      }),
    [setParams],
  );

  const setStatus = useCallback(
    (value?: number) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value === undefined) next.delete("status");
        else next.set("status", String(value));
        next.delete("page");
        return next;
      }),
    [setParams],
  );

  const list = useQuery({
    queryKey: queryKeys.aftersaleList(shopIds, { view, status, page }),
    queryFn: () =>
      view === "todo"
        ? api.get<PageData>("/api/aftersale/todo", { shop_ids: shopIds, page, page_size: PAGE_SIZE })
        : api.get<PageData>("/api/aftersale", {
            shop_ids: shopIds, status, page, page_size: PAGE_SIZE,
          }),
    placeholderData: keepPreviousData,
  });

  // 切换按钮上的数量：两个视图各取一条，只用 total（本地已同步的单数，不随状态筛选变）
  const totals = useQuery({
    queryKey: queryKeys.aftersaleTotals(shopIds),
    queryFn: async () => {
      const [todo, all] = await Promise.all([
        api.get<PageData>("/api/aftersale/todo", { shop_ids: shopIds, page: 1, page_size: 1 }),
        api.get<PageData>("/api/aftersale", { shop_ids: shopIds, page: 1, page_size: 1 }),
      ]);
      return { todo: todo.total, all: all.total } satisfies Record<View, number>;
    },
  });

  const statuses = useQuery({
    queryKey: queryKeys.aftersaleStatuses(shopIds),
    queryFn: () => api.get<StatusesResponse>("/api/aftersale/statuses", { shop_ids: shopIds }),
  });

  const counts = useQuery(metricQueries.aftersaleCounts(shopIds));

  const sync = useAftersaleSync();
  const names = useMemo(
    () => new Map((shops.data ?? []).map((s) => [s.id, s.name])),
    [shops.data],
  );

  return {
    shopsState: shops.isLoading
      ? ("loading" as const)
      : shops.isError
        ? ("error" as const)
        : (shops.data ?? []).length === 0
          ? ("empty" as const)
          : ("ready" as const),
    retryShops: () => void shops.refetch(),
    shopName: (id: number) => names.get(id) ?? `店铺 ${id}`,
    view,
    setView: (value: View) => update({ view: value }),
    status,
    setStatus,
    page,
    setPage: (value: number) => update({ page: value }),
    list,
    viewTotals: totals.data,
    statusOptions: statuses.data?.items ?? [],
    counts,
    sync,
  };
}

export type AftersalePageState = ReturnType<typeof useAftersalePage>;

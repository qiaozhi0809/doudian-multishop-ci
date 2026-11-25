import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import { actionErrorMessage } from "../logic/label-messages";
import {
  summarizePrint,
  type PrinterStatus,
  type WaybillPrint,
} from "../logic/print-status";

const STATUS_STALE_MS = 25_000; // flows 10：组件状态缓存约 30 秒
const STATUS_POLL_MS = 30_000;
const JOB_POLL_MS = 1_500;

/** 打印：组件状态探测、提交打印批次、面单打印状态（有排队任务时自动轮询）。 */
export function usePrint(visibleWaybillIds: number[]) {
  const client = useQueryClient();
  const [printing, setPrinting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: queryKeys.printStatus(),
    queryFn: () => api.get<PrinterStatus>("/api/print/status"),
    staleTime: STATUS_STALE_MS,
    refetchInterval: STATUS_POLL_MS,
    retry: false,
  });

  const rowsQuery = useQuery({
    queryKey: queryKeys.printWaybills(visibleWaybillIds),
    queryFn: () =>
      api.get<components["schemas"]["WaybillPrintList"]>("/api/print/waybills", {
        waybill_ids: visibleWaybillIds,
      }),
    enabled: visibleWaybillIds.length > 0,
    refetchInterval: (query) => {
      const rows = query.state.data?.items ?? [];
      return rows.some((row) => row.job?.status === "queued") ? JOB_POLL_MS : false;
    },
  });

  useEventSubscription("print_progress", () => {
    void client.invalidateQueries({ queryKey: queryKeys.printWaybillsRoot() });
  });
  useEventSubscription("print_done", () => {
    void client.invalidateQueries({ queryKey: queryKeys.printWaybillsRoot() });
    void client.invalidateQueries({ queryKey: queryKeys.labelPoolRoot() });
  });

  const mutation = useMutation({
    mutationFn: (ids: number[]) =>
      api.post<components["schemas"]["PrintStarted"]>("/api/print/jobs", {
        waybill_ids: ids,
      }),
    onMutate: () => {
      setError(null);
      setPrinting(true);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.printWaybillsRoot() });
    },
    onError: (e) => setError(actionErrorMessage(e)),
    onSettled: () => setPrinting(false),
  });

  const rows = useMemo(() => rowsQuery.data?.items ?? [], [rowsQuery.data]);
  const rowsByWaybill = useMemo(
    () => new Map<number, WaybillPrint>(rows.map((row) => [row.waybill_id, row])),
    [rows],
  );

  const print = useCallback(
    (ids: number[]) => {
      if (ids.length > 0) mutation.mutate(ids);
    },
    [mutation],
  );

  return {
    status: statusQuery.data,
    rows,
    rowsByWaybill,
    summary: summarizePrint(rows),
    print,
    printing,
    error,
    clearError: () => setError(null),
  };
}

import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import { actionErrorMessage, type ShipCheck } from "../logic/ship-messages";
import {
  applyDone,
  initialProgress,
  mergeProgress,
  type ProgressState,
  type ShipDoneEvent,
  type ShipProgressEvent,
} from "../logic/ship-progress";

interface ShipVars {
  orderIds: number[];
  acknowledged: boolean;
}

/** 发货：发货前检查 → 二次确认 → 提交批次；逐单结果由 SSE 汇总。 */
export function useShippingActions() {
  const client = useQueryClient();
  const [check, setCheck] = useState<ShipCheck | null>(null);
  const [requestedIds, setRequestedIds] = useState<number[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState>(initialProgress());
  const [error, setError] = useState<string | null>(null);
  const [simulated, setSimulated] = useState(false);

  const checkMutation = useMutation({
    mutationFn: (orderIds: number[]) =>
      api.post<ShipCheck>("/api/shipping/check", { order_ids: orderIds }),
    onSuccess: (data, orderIds) => {
      setCheck(data);
      setRequestedIds(orderIds);
      setSimulated(false);
      setError(null);
    },
    onError: (e) => setError(actionErrorMessage(e)),
  });

  const shipMutation = useMutation({
    mutationFn: (vars: ShipVars) =>
      api.post<components["schemas"]["ShipStartedOut"]>("/api/shipping/ship", {
        order_ids: vars.orderIds,
        double_check_ack: vars.acknowledged,
      }),
    onSuccess: (data) => {
      setCheck(null);
      setSimulated(data.simulated);
      // 演练模式：没有真实发货，不进入进度等待（SSE 不会有逐单事件）
      setBatchId(data.simulated ? null : data.batch_id);
      setProgress(initialProgress());
      setError(null);
    },
    onError: (e) => setError(actionErrorMessage(e)),
  });

  useEventSubscription<ShipProgressEvent>("ship_progress", (event) => {
    if (event.batch_id !== batchId) return;
    setProgress((state) => mergeProgress(state, event));
  });

  useEventSubscription<ShipDoneEvent>("ship_done", (event) => {
    if (event.batch_id !== batchId) return;
    setProgress((state) => applyDone(state, event));
    void client.invalidateQueries({ queryKey: queryKeys.labelPoolRoot() });
    void client.invalidateQueries({ queryKey: queryKeys.ordersRoot() });
  });

  const openCheck = useCallback(
    (orderIds: number[]) => checkMutation.mutate(orderIds),
    [checkMutation],
  );

  const confirm = useCallback(() => {
    if (!check) return;
    // 重试时先清掉上次的失败原因
    setError(null);
    shipMutation.mutate({
      orderIds: requestedIds,
      acknowledged: check.double_check_total > 0,
    });
  }, [check, requestedIds, shipMutation]);

  return {
    check,
    progress,
    batchId,
    error,
    simulated,
    clearError: () => setError(null),
    checkBusy: checkMutation.isPending,
    shipBusy: shipMutation.isPending,
    running: batchId !== null && !progress.done,
    openCheck,
    closeCheck: () => {
      setCheck(null);
      setError(null);
    },
    confirm,
  };
}

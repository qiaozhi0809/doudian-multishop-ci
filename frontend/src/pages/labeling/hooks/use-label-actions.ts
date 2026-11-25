import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import { actionErrorMessage } from "../logic/label-messages";
import {
  applyDone,
  executePath,
  initialProgress,
  mergeProgress,
  previewPath,
  type DoneEvent,
  type ExecMode,
  type PreviewResponse,
  type ProgressEvent,
  type ProgressState,
} from "../logic/preview-summary";

interface PreviewVars {
  mode: ExecMode;
  orderIds: number[];
}

interface ExecuteVars {
  previewId: string;
  mode: ExecMode;
}

/** 两步提交：预览 → 执行；执行进度由 SSE 汇总，结束后让订单池与订单页失效。 */
export function useLabelActions() {
  const client = useQueryClient();
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewMode, setPreviewMode] = useState<ExecMode>("obtain");
  const [runningPreviewId, setRunningPreviewId] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressState>(initialProgress());
  const [error, setError] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: (vars: PreviewVars) =>
      api.post<PreviewResponse>(previewPath(vars.mode), { order_ids: vars.orderIds }),
    onSuccess: (data, vars) => {
      setPreview(data);
      setPreviewMode(vars.mode);
      setProgress(initialProgress());
      setRunningPreviewId(null);
      setError(null);
    },
    onError: (e) => setError(actionErrorMessage(e)),
  });

  const executeMutation = useMutation({
    mutationFn: (vars: ExecuteVars) =>
      api.post<components["schemas"]["ExecuteStarted"]>(executePath(vars.mode), {
        preview_id: vars.previewId,
      }),
    onSuccess: (_data, vars) => {
      setPreview(null);
      setRunningPreviewId(vars.previewId);
      setProgress(initialProgress());
      setError(null);
    },
    onError: (e) => setError(actionErrorMessage(e)),
  });

  useEventSubscription<ProgressEvent>("label_progress", (event) => {
    if (event.preview_id !== runningPreviewId) return;
    setProgress((state) => mergeProgress(state, event));
    void client.invalidateQueries({ queryKey: queryKeys.labelPoolRoot() });
  });

  useEventSubscription<DoneEvent>("label_done", (event) => {
    if (event.preview_id !== runningPreviewId) return;
    setProgress((state) => applyDone(state, event));
    void client.invalidateQueries({ queryKey: queryKeys.labelPoolRoot() });
    void client.invalidateQueries({ queryKey: queryKeys.ordersRoot() });
  });

  const openPreview = useCallback(
    (mode: ExecMode, orderIds: number[]) => previewMutation.mutate({ mode, orderIds }),
    [previewMutation],
  );

  const execute = useCallback(() => {
    if (preview) executeMutation.mutate({ previewId: preview.preview_id, mode: previewMode });
  }, [preview, previewMode, executeMutation]);

  return {
    preview,
    previewMode,
    progress,
    error,
    clearError: () => setError(null),
    previewBusy: previewMutation.isPending,
    executeBusy: executeMutation.isPending,
    running: runningPreviewId !== null && !progress.done,
    openPreview,
    closePreview: () => setPreview(null),
    execute,
  };
}

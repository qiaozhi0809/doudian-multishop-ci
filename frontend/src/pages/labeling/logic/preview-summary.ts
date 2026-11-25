import type { components } from "@/lib/api-types";

export type ExecMode = "obtain" | "fetch_and_ship" | "void";
export type PreviewResponse =
  | components["schemas"]["LabelPreviewResponse"]
  | components["schemas"]["VoidPreviewResponse"];

export type ProgressResult = "success" | "failed" | "verifying" | "skipped";

export interface ProgressEvent {
  preview_id: string;
  mode: string;
  order_id: number | null;
  order_no: string | null;
  result: ProgressResult;
  tracking_no: string | null;
  reason: string | null;
}

export interface DoneEvent {
  preview_id: string;
  mode: string;
  ok: number;
  failed: number;
  verifying: number;
  skipped: number;
}

export interface ProgressRow {
  orderId: number;
  orderNo: string;
  result: ProgressResult;
  trackingNo: string | null;
  reason: string | null;
}

export interface ProgressState {
  rows: Record<number, ProgressRow>;
  done: boolean;
  ok: number;
  failed: number;
  verifying: number;
  skipped: number;
}

export const MODE_LABELS: Record<ExecMode, string> = {
  obtain: "打单",
  fetch_and_ship: "打单并发货",
  void: "作废面单",
};

export const initialProgress = (): ProgressState => ({
  rows: {},
  done: false,
  ok: 0,
  failed: 0,
  verifying: 0,
  skipped: 0,
});

function recount(rows: Record<number, ProgressRow>) {
  let ok = 0;
  let failed = 0;
  let verifying = 0;
  let skipped = 0;
  for (const row of Object.values(rows)) {
    if (row.result === "success") ok += 1;
    else if (row.result === "failed") failed += 1;
    else if (row.result === "verifying") verifying += 1;
    else skipped += 1;
  }
  return { ok, failed, verifying, skipped };
}

/** 逐单事件：同一订单以最后一次结果为准（重试 / 查回覆盖先前结果）。 */
export function mergeProgress(state: ProgressState, event: ProgressEvent): ProgressState {
  if (event.order_id === null) return state;
  const rows: Record<number, ProgressRow> = {
    ...state.rows,
    [event.order_id]: {
      orderId: event.order_id,
      orderNo: event.order_no ?? "",
      result: event.result,
      trackingNo: event.tracking_no,
      reason: event.reason,
    },
  };
  return { ...state, rows, ...recount(rows) };
}

/** 汇总事件：结束状态以服务端计数为准。 */
export function applyDone(state: ProgressState, event: DoneEvent): ProgressState {
  return {
    ...state,
    done: true,
    ok: event.ok,
    failed: event.failed,
    verifying: event.verifying,
    skipped: event.skipped,
  };
}

export interface PreviewTotals {
  ready: number;
  blocked: number;
  shops: number;
}

export function previewTotals(preview: PreviewResponse): PreviewTotals {
  return {
    ready: preview.total_ready,
    blocked: preview.total_blocked,
    shops: preview.shops.length,
  };
}

export const previewPath = (mode: ExecMode): string =>
  mode === "void" ? "/api/labels/void/preview" : `/api/labels/${mode === "fetch_and_ship" ? "fetch-and-ship/" : ""}preview`;

export const executePath = (mode: ExecMode): string =>
  mode === "void"
    ? "/api/labels/void/execute"
    : `/api/labels/${mode === "fetch_and_ship" ? "fetch-and-ship/" : ""}execute`;

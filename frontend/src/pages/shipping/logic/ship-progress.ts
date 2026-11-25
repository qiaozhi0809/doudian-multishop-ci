export type ProgressResult = "success" | "failed" | "skipped";

export interface ShipProgressEvent {
  batch_id: string;
  shop_id: number;
  order_id: number | null;
  order_no: string | null;
  result: ProgressResult;
  tracking_no: string | null;
  reason: string | null;
}

export interface ShipDoneEvent {
  batch_id: string;
  ok: number;
  failed: number;
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
  skipped: number;
}

export const initialProgress = (): ProgressState => ({
  rows: {},
  done: false,
  ok: 0,
  failed: 0,
  skipped: 0,
});

function recount(rows: Record<number, ProgressRow>) {
  let ok = 0;
  let failed = 0;
  let skipped = 0;
  for (const row of Object.values(rows)) {
    if (row.result === "success") ok += 1;
    else if (row.result === "failed") failed += 1;
    else skipped += 1;
  }
  return { ok, failed, skipped };
}

/** 逐单事件：同一订单以最后一次结果为准。 */
export function mergeProgress(
  state: ProgressState,
  event: ShipProgressEvent,
): ProgressState {
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
export function applyDone(state: ProgressState, event: ShipDoneEvent): ProgressState {
  return {
    ...state,
    done: true,
    ok: event.ok,
    failed: event.failed,
    skipped: event.skipped,
  };
}

export function progressTitle(state: ProgressState): string {
  const prefix = state.done ? "发货完成" : "发货中";
  return `${prefix}：成功 ${state.ok}，失败 ${state.failed}，跳过 ${state.skipped}`;
}

export function failedRows(state: ProgressState): ProgressRow[] {
  return Object.values(state.rows)
    .filter((row) => row.result === "failed")
    .sort((a, b) => a.orderNo.localeCompare(b.orderNo));
}

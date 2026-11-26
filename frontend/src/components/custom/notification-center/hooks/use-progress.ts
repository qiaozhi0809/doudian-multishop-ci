import { useSyncExternalStore } from "react";
import { useEventSubscription } from "@/lib/use-events";
import { applyProgressEvent, emptyProgress, type ProgressEvent, type ProgressItem, type ProgressState } from "../logic/progress";

type Listener = () => void;
const listeners = new Set<Listener>();
let state: ProgressState = emptyProgress();

/** 全应用共用一份进度：页面切换不丢，SSE 事件直接推进。 */
export const progressStore = {
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getSnapshot: (): ProgressState => state,
  publish(event: ProgressEvent): void {
    state = applyProgressEvent(state, event);
    for (const listener of listeners) listener();
  },
  /** 测试用：恢复初始状态。 */
  reset(): void {
    state = emptyProgress();
    for (const listener of listeners) listener();
  },
};

interface LabelProgress { preview_id: string; mode: string; order_id: number | null; result: string }
interface LabelDone { preview_id: string; ok: number; failed: number; verifying: number; skipped: number }
interface ShipProgress { batch_id: string; order_id: number | null; result: string }
interface ShipDone { batch_id: string; ok: number; failed: number; skipped: number }
interface PrintProgress { job_id: number; result: string }
interface PrintDone { ok: number; failed: number; manual: number; skipped: number }

const { publish } = progressStore;

/** 订阅批量任务的 SSE 进度事件，返回进行中的任务；结束的任务已移除。 */
export function useProgress(): ProgressItem[] {
  const current = useSyncExternalStore(progressStore.subscribe, progressStore.getSnapshot, progressStore.getSnapshot);

  useEventSubscription<LabelProgress>("label_progress", (e) =>
    publish({ type: "label_progress", previewId: e.preview_id, mode: e.mode, orderId: e.order_id, result: e.result }),
  );
  useEventSubscription<LabelDone>("label_done", (e) =>
    publish({ type: "label_done", previewId: e.preview_id, ok: e.ok, failed: e.failed, verifying: e.verifying, skipped: e.skipped }),
  );
  useEventSubscription<ShipProgress>("ship_progress", (e) =>
    publish({ type: "ship_progress", batchId: e.batch_id, orderId: e.order_id, result: e.result }),
  );
  useEventSubscription<ShipDone>("ship_done", (e) =>
    publish({ type: "ship_done", batchId: e.batch_id, ok: e.ok, failed: e.failed, skipped: e.skipped }),
  );
  useEventSubscription<PrintProgress>("print_progress", (e) =>
    publish({ type: "print_progress", jobId: e.job_id, result: e.result }),
  );
  useEventSubscription<PrintDone>("print_done", (e) =>
    publish({ type: "print_done", ok: e.ok, failed: e.failed, manual: e.manual, skipped: e.skipped }),
  );

  return current.tasks;
}

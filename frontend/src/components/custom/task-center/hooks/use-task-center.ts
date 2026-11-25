import { useSyncExternalStore } from "react";
import { useEventSubscription } from "@/lib/use-events";
import { runningCount } from "../logic/task-log";
import { taskStore } from "../logic/task-store";

interface LabelProgress {
  preview_id: string;
  mode: string;
  order_id: number | null;
  result: string;
}
interface LabelDone {
  preview_id: string;
  ok: number;
  failed: number;
  verifying: number;
  skipped: number;
}
interface ShipProgress {
  batch_id: string;
  order_id: number | null;
  result: string;
}
interface ShipDone {
  batch_id: string;
  ok: number;
  failed: number;
  skipped: number;
}
interface PrintProgress {
  job_id: number;
  result: string;
}
interface PrintDone {
  ok: number;
  failed: number;
  manual: number;
  skipped: number;
}
interface DeadlineWarning {
  count: number;
  warn_hours: number;
}

/** 订阅任务相关的 SSE 事件，推进全应用共用的任务状态。 */
export function useTaskCenter() {
  const state = useSyncExternalStore(taskStore.subscribe, taskStore.getSnapshot, taskStore.getSnapshot);

  useEventSubscription<LabelProgress>("label_progress", (e) =>
    taskStore.publish({ type: "label_progress", previewId: e.preview_id, mode: e.mode, orderId: e.order_id, result: e.result }),
  );
  useEventSubscription<LabelDone>("label_done", (e) =>
    taskStore.publish({
      type: "label_done",
      previewId: e.preview_id,
      ok: e.ok,
      failed: e.failed,
      verifying: e.verifying,
      skipped: e.skipped,
    }),
  );
  useEventSubscription<ShipProgress>("ship_progress", (e) =>
    taskStore.publish({ type: "ship_progress", batchId: e.batch_id, orderId: e.order_id, result: e.result }),
  );
  useEventSubscription<ShipDone>("ship_done", (e) =>
    taskStore.publish({ type: "ship_done", batchId: e.batch_id, ok: e.ok, failed: e.failed, skipped: e.skipped }),
  );
  useEventSubscription<PrintProgress>("print_progress", (e) =>
    taskStore.publish({ type: "print_progress", jobId: e.job_id, result: e.result }),
  );
  useEventSubscription<PrintDone>("print_done", (e) =>
    taskStore.publish({ type: "print_done", ok: e.ok, failed: e.failed, manual: e.manual, skipped: e.skipped }),
  );
  useEventSubscription<DeadlineWarning>("ship_deadline_warning", (e) =>
    taskStore.publish({ type: "deadline_warning", count: e.count, warnHours: e.warn_hours }),
  );

  return {
    tasks: state.tasks,
    runningCount: runningCount(state.tasks),
    dismiss: taskStore.dismiss,
    clearFinished: taskStore.clearFinished,
  };
}

/** 进行中批量任务的纯状态机（迁自任务中心）：SSE 进度事件 → 取号 / 发货 / 打印进度；结束即移除，结果由通知承担。 */

export type ProgressKind = "label" | "ship" | "print";

export interface ProgressCounts {
  ok: number;
  failed: number;
  /** 需要人工跟进：取号「待核实」、打印「需补打」 */
  waiting: number;
  skipped: number;
}

export interface ProgressItem {
  id: string;
  kind: ProgressKind;
  title: string;
  counts: ProgressCounts;
  /** 已计入结果的订单 / 任务 id，同一实体的重试事件不重复计数 */
  seen: string[];
}

export interface ProgressState {
  tasks: ProgressItem[];
  /** 生成打印任务 id 用的序号，保证纯函数可测 */
  seq: number;
}

export type ProgressEvent =
  | { type: "label_progress"; previewId: string; mode: string; orderId: number | null; result: string }
  | { type: "label_done"; previewId: string; ok: number; failed: number; verifying: number; skipped: number }
  | { type: "ship_progress"; batchId: string; orderId: number | null; result: string }
  | { type: "ship_done"; batchId: string; ok: number; failed: number; skipped: number }
  | { type: "print_progress"; jobId: number; result: string }
  | { type: "print_done"; ok: number; failed: number; manual: number; skipped: number };

export const PROGRESS_LIMIT = 8;

const MODE_TITLES: Record<string, string> = {
  obtain: "打单",
  fetch_and_ship: "打单并发货",
  void: "作废面单",
};

export const emptyProgress = (): ProgressState => ({ tasks: [], seq: 0 });

const emptyCounts = (): ProgressCounts => ({ ok: 0, failed: 0, waiting: 0, skipped: 0 });

function bump(counts: ProgressCounts, result: string): ProgressCounts {
  switch (result) {
    case "success":
      return { ...counts, ok: counts.ok + 1 };
    case "failed":
      return { ...counts, failed: counts.failed + 1 };
    case "verifying":
    case "manual":
      return { ...counts, waiting: counts.waiting + 1 };
    case "skipped":
      return { ...counts, skipped: counts.skipped + 1 };
    default:
      return counts;
  }
}

function upsert(
  state: ProgressState,
  find: (task: ProgressItem) => boolean,
  create: (seq: number) => Omit<ProgressItem, "counts" | "seen">,
  entityKey: string,
  result: string,
): ProgressState {
  let { tasks, seq } = state;
  let index = tasks.findIndex(find);
  if (index < 0) {
    seq += 1;
    tasks = [{ ...create(seq), counts: emptyCounts(), seen: [] }, ...tasks].slice(0, PROGRESS_LIMIT);
    index = 0;
  }
  const task = tasks[index];
  if (task.seen.includes(entityKey)) return { tasks, seq };
  const updated = { ...task, counts: bump(task.counts, result), seen: [...task.seen, entityKey] };
  return { tasks: tasks.map((item, i) => (i === index ? updated : item)), seq };
}

function remove(state: ProgressState, find: (task: ProgressItem) => boolean): ProgressState {
  const index = state.tasks.findIndex(find);
  if (index < 0) return state;
  return { ...state, tasks: state.tasks.filter((_, i) => i !== index) };
}

export function applyProgressEvent(state: ProgressState, event: ProgressEvent): ProgressState {
  switch (event.type) {
    case "label_progress": {
      if (event.orderId === null) return state;
      const id = `label:${event.previewId}`;
      const title = MODE_TITLES[event.mode] ?? "打单";
      return upsert(state, (t) => t.id === id, () => ({ id, kind: "label", title }), String(event.orderId), event.result);
    }
    case "label_done":
      return remove(state, (t) => t.id === `label:${event.previewId}`);
    case "ship_progress": {
      if (event.orderId === null) return state;
      const id = `ship:${event.batchId}`;
      return upsert(state, (t) => t.id === id, () => ({ id, kind: "ship", title: "发货" }), String(event.orderId), event.result);
    }
    case "ship_done":
      return remove(state, (t) => t.id === `ship:${event.batchId}`);
    case "print_progress":
      return upsert(
        state,
        (t) => t.kind === "print",
        (seq) => ({ id: `print:${seq}`, kind: "print", title: "打印面单" }),
        String(event.jobId),
        event.result,
      );
    case "print_done":
      return remove(state, (t) => t.kind === "print");
  }
}

const WAITING_LABEL: Record<ProgressKind, string> = {
  label: "待核实",
  ship: "待处理",
  print: "需补打",
};

/** 结果摘要：只列非零项；还没有结果时显示等待。 */
export function countsText(task: ProgressItem): string {
  const parts: string[] = [];
  if (task.counts.ok > 0) parts.push(`成功 ${task.counts.ok}`);
  if (task.counts.failed > 0) parts.push(`失败 ${task.counts.failed}`);
  if (task.counts.waiting > 0) parts.push(`${WAITING_LABEL[task.kind]} ${task.counts.waiting}`);
  if (task.counts.skipped > 0) parts.push(`跳过 ${task.counts.skipped}`);
  return parts.length === 0 ? "等待结果" : parts.join("，");
}

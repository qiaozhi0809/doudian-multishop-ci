/** 任务中心的纯状态机：SSE 事件 → 进行中的取号 / 打印 / 发货任务。 */

export type TaskKind = "label" | "ship" | "print";
export type TaskStatus = "running" | "done";

export interface TaskCounts {
  ok: number;
  failed: number;
  /** 需要人工跟进：取号「待核实」、打印「需补打」 */
  waiting: number;
  skipped: number;
}

export interface TaskItem {
  id: string;
  kind: TaskKind;
  title: string;
  status: TaskStatus;
  counts: TaskCounts;
  /** 已计入结果的订单 / 任务 id，同一实体的重试事件不重复计数 */
  seen: string[];
}

export interface TaskCenterState {
  tasks: TaskItem[];
  /** 生成任务 id 用的序号，保证纯函数可测 */
  seq: number;
}

export type TaskEvent =
  | { type: "label_progress"; previewId: string; mode: string; orderId: number | null; result: string }
  | { type: "label_done"; previewId: string; ok: number; failed: number; verifying: number; skipped: number }
  | { type: "ship_progress"; batchId: string; orderId: number | null; result: string }
  | { type: "ship_done"; batchId: string; ok: number; failed: number; skipped: number }
  | { type: "print_progress"; jobId: number; result: string }
  | { type: "print_done"; ok: number; failed: number; manual: number; skipped: number }
  | { type: "dismiss"; id: string }
  | { type: "clear_finished" };

export const TASK_LIMIT = 8;

const MODE_TITLES: Record<string, string> = {
  obtain: "取号（打面单）",
  fetch_and_ship: "取号并发货",
  void: "作废面单",
};

export const emptyTaskCenter = (): TaskCenterState => ({ tasks: [], seq: 0 });

export const emptyCounts = (): TaskCounts => ({ ok: 0, failed: 0, waiting: 0, skipped: 0 });

function bump(counts: TaskCounts, result: string): TaskCounts {
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

/** 最多保留 8 条：先丢最早的已完成任务，再丢最早的进行中任务。 */
function trim(tasks: TaskItem[]): TaskItem[] {
  const next = [...tasks];
  while (next.length > TASK_LIMIT) {
    const finished = next.map((task) => task.status).lastIndexOf("done");
    next.splice(finished >= 0 ? finished : next.length - 1, 1);
  }
  return next;
}

function upsertProgress(
  state: TaskCenterState,
  id: string,
  kind: TaskKind,
  title: string,
  entityKey: string,
  result: string,
  preferRunningPrint = false,
): TaskCenterState {
  let tasks = state.tasks;
  let seq = state.seq;
  let index = preferRunningPrint
    ? tasks.findIndex((task) => task.kind === "print" && task.status === "running")
    : tasks.findIndex((task) => task.id === id);
  if (index < 0) {
    seq += 1;
    tasks = [
      { id: preferRunningPrint ? `print:${seq}` : id, kind, title, status: "running", counts: emptyCounts(), seen: [] },
      ...tasks,
    ];
    index = 0;
  }
  const task = tasks[index];
  if (task.seen.includes(entityKey)) return { tasks, seq };
  const updated: TaskItem = {
    ...task,
    counts: bump(task.counts, result),
    seen: [...task.seen, entityKey],
  };
  return { tasks: trim(tasks.map((item, i) => (i === index ? updated : item))), seq };
}

function finish(
  state: TaskCenterState,
  find: (task: TaskItem) => boolean,
  counts: TaskCounts,
): TaskCenterState {
  const index = state.tasks.findIndex((task) => task.status === "running" && find(task));
  if (index < 0) return state;
  const tasks = state.tasks.map((task, i) =>
    i === index ? { ...task, status: "done" as const, counts } : task,
  );
  return { ...state, tasks };
}

export function applyTaskEvent(state: TaskCenterState, event: TaskEvent): TaskCenterState {
  switch (event.type) {
    case "dismiss":
      return { ...state, tasks: state.tasks.filter((task) => task.id !== event.id) };
    case "clear_finished":
      return { ...state, tasks: state.tasks.filter((task) => task.status === "running") };
    case "label_progress": {
      if (event.orderId === null) return state;
      return upsertProgress(
        state,
        `label:${event.previewId}`,
        "label",
        MODE_TITLES[event.mode] ?? "打单",
        String(event.orderId),
        event.result,
      );
    }
    case "label_done":
      return finish(
        state,
        (task) => task.id === `label:${event.previewId}`,
        { ok: event.ok, failed: event.failed, waiting: event.verifying, skipped: event.skipped },
      );
    case "ship_progress": {
      if (event.orderId === null) return state;
      return upsertProgress(
        state,
        `ship:${event.batchId}`,
        "ship",
        "发货",
        String(event.orderId),
        event.result,
      );
    }
    case "ship_done":
      return finish(
        state,
        (task) => task.id === `ship:${event.batchId}`,
        { ok: event.ok, failed: event.failed, waiting: 0, skipped: event.skipped },
      );
    case "print_progress":
      return upsertProgress(state, "print", "print", "打印面单", String(event.jobId), event.result, true);
    case "print_done":
      return finish(state, (task) => task.kind === "print", {
        ok: event.ok,
        failed: event.failed,
        waiting: event.manual,
        skipped: event.skipped,
      });
  }
}

export const runningCount = (tasks: TaskItem[]): number =>
  tasks.filter((task) => task.status === "running").length;

const WAITING_LABEL: Record<TaskKind, string> = {
  label: "待核实",
  ship: "待处理",
  print: "需补打",
};

/** 结果摘要：只列非零项；还没有结果时提示等待。 */
export function countsText(task: TaskItem): string {
  const parts: string[] = [];
  if (task.counts.ok > 0) parts.push(`成功 ${task.counts.ok}`);
  if (task.counts.failed > 0) parts.push(`失败 ${task.counts.failed}`);
  if (task.counts.waiting > 0) parts.push(`${WAITING_LABEL[task.kind]} ${task.counts.waiting}`);
  if (task.counts.skipped > 0) parts.push(`跳过 ${task.counts.skipped}`);
  if (parts.length === 0) return task.status === "running" ? "等待结果" : "没有结果";
  return parts.join("，");
}

export function statusText(task: TaskItem): string {
  if (task.status === "running") return "进行中";
  return task.counts.failed > 0 ? "完成，有失败" : "完成";
}

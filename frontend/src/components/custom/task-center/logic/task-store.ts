import { applyTaskEvent, emptyTaskCenter, type TaskCenterState, type TaskEvent } from "./task-log";

type Listener = () => void;

const listeners = new Set<Listener>();
let state: TaskCenterState = emptyTaskCenter();

function set(next: TaskCenterState): void {
  state = next;
  for (const listener of listeners) listener();
}

/** 全应用共用一个任务状态：页面切换不丢进度，SSE 事件直接推进。 */
export const taskStore = {
  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getSnapshot(): TaskCenterState {
    return state;
  },
  publish(event: TaskEvent): void {
    set(applyTaskEvent(state, event));
  },
  clearFinished(): void {
    set(applyTaskEvent(state, { type: "clear_finished" }));
  },
  dismiss(id: string): void {
    set(applyTaskEvent(state, { type: "dismiss", id }));
  },
  /** 测试用：恢复初始状态。 */
  reset(): void {
    set(emptyTaskCenter());
  },
};

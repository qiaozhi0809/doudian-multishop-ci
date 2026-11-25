import { act, renderHook } from "@testing-library/react";
import { FakeEventSource } from "@/test/fake-event-source";
import { taskStore } from "../logic/task-store";
import { useTaskCenter } from "./use-task-center";

let restore: () => void;
beforeEach(() => {
  taskStore.reset();
  restore = FakeEventSource.install();
});
afterEach(() => {
  restore();
});

describe("任务中心的 SSE 绑定", () => {
  it("label_progress 建立进行中任务，label_done 收尾", () => {
    const { result } = renderHook(() => useTaskCenter());
    act(() =>
      FakeEventSource.latest().emit("label_progress", {
        preview_id: "p1",
        mode: "obtain",
        order_id: 1,
        result: "success",
      }),
    );
    expect(result.current.tasks[0]).toMatchObject({ id: "label:p1", status: "running" });
    expect(result.current.runningCount).toBe(1);

    act(() =>
      FakeEventSource.latest().emit("label_done", {
        preview_id: "p1",
        ok: 1,
        failed: 0,
        verifying: 0,
        skipped: 0,
      }),
    );
    expect(result.current.tasks[0]).toMatchObject({ status: "done", counts: { ok: 1 } });
    expect(result.current.runningCount).toBe(0);
  });

  it("ship_progress / ship_done 与 print_progress / print_done 都能推进任务", () => {
    const { result } = renderHook(() => useTaskCenter());
    act(() => FakeEventSource.latest().emit("ship_progress", { batch_id: "b1", order_id: 2, result: "success" }));
    act(() => FakeEventSource.latest().emit("ship_done", { batch_id: "b1", ok: 1, failed: 0, skipped: 0 }));
    act(() => FakeEventSource.latest().emit("print_progress", { job_id: 9, result: "success" }));
    act(() =>
      FakeEventSource.latest().emit("print_done", { ok: 1, failed: 0, manual: 0, skipped: 0 }),
    );
    expect(result.current.tasks).toHaveLength(2);
    expect(result.current.tasks.every((task) => task.status === "done")).toBe(true);
  });

  it("清除动作通过同一个 store 生效", () => {
    const { result } = renderHook(() => useTaskCenter());
    act(() => FakeEventSource.latest().emit("ship_progress", { batch_id: "b1", order_id: 2, result: "success" }));
    act(() => FakeEventSource.latest().emit("ship_done", { batch_id: "b1", ok: 1, failed: 0, skipped: 0 }));
    act(() => result.current.clearFinished());
    expect(result.current.tasks).toEqual([]);
  });
});

import { act, renderHook } from "@testing-library/react";
import { FakeEventSource } from "@/test/fake-event-source";
import { progressStore, useProgress, useProgressSubscriptions } from "./use-progress";

let restore: () => void;
beforeEach(() => {
  progressStore.reset();
  restore = FakeEventSource.install();
});
afterEach(() => restore());

/** 订阅只在通知中心根部挂一次；其余地方只读 store。 */
function useBoth() {
  useProgressSubscriptions();
  return useProgress();
}

describe("进行中任务的 SSE 绑定", () => {
  it("label_progress 建立任务，label_done 后移除", () => {
    const { result } = renderHook(() => useBoth());
    act(() =>
      FakeEventSource.latest().emit("label_progress", { preview_id: "p1", mode: "fetch_and_ship", order_id: 1, result: "success" }),
    );
    expect(result.current[0]).toMatchObject({ id: "label:p1", title: "打单并发货", counts: { ok: 1 } });
    act(() =>
      FakeEventSource.latest().emit("label_done", { preview_id: "p1", ok: 1, failed: 0, verifying: 0, skipped: 0 }),
    );
    expect(result.current).toEqual([]);
  });

  it("ship 与 print 事件推进并在 done 后移除", () => {
    const { result } = renderHook(() => useBoth());
    act(() => FakeEventSource.latest().emit("ship_progress", { batch_id: "b1", order_id: 2, result: "success" }));
    act(() => FakeEventSource.latest().emit("print_progress", { job_id: 9, result: "success" }));
    expect(result.current).toHaveLength(2);
    act(() => FakeEventSource.latest().emit("ship_done", { batch_id: "b1", ok: 1, failed: 0, skipped: 0 }));
    act(() => FakeEventSource.latest().emit("print_done", { ok: 1, failed: 0, manual: 0, skipped: 0 }));
    expect(result.current).toEqual([]);
  });

  it("页面间共用同一份进度", () => {
    const first = renderHook(() => useBoth());
    act(() => FakeEventSource.latest().emit("ship_progress", { batch_id: "b1", order_id: 2, result: "success" }));
    const second = renderHook(() => useProgress());
    expect(second.result.current).toHaveLength(1);
    first.unmount();
  });

  it("useProgress 只读 store，不建立 SSE 订阅", () => {
    renderHook(() => useProgress());
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});

import { applyProgressEvent, countsText, emptyProgress, PROGRESS_LIMIT, type ProgressState } from "./progress";

const labelProgress = (previewId: string, orderId: number | null, result = "success") =>
  ({ type: "label_progress", previewId, mode: "obtain", orderId, result }) as const;

function run(events: Parameters<typeof applyProgressEvent>[1][]): ProgressState {
  return events.reduce(applyProgressEvent, emptyProgress());
}

describe("进行中批量任务", () => {
  it("label_progress 建立任务并按订单计数，重复订单不重复计", () => {
    const state = run([labelProgress("p1", 1), labelProgress("p1", 1), labelProgress("p1", 2, "failed")]);
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0]).toMatchObject({ id: "label:p1", kind: "label", title: "打单", counts: { ok: 1, failed: 1 } });
  });

  it("没有订单 id 的进度事件忽略", () => {
    expect(run([labelProgress("p1", null)]).tasks).toEqual([]);
  });

  it("label_done 后从列表移除", () => {
    const state = run([
      labelProgress("p1", 1),
      labelProgress("p2", 2),
      { type: "label_done", previewId: "p1", ok: 1, failed: 0, verifying: 0, skipped: 0 },
    ]);
    expect(state.tasks.map((t) => t.id)).toEqual(["label:p2"]);
  });

  it("ship_done 后移除对应批次", () => {
    const state = run([
      { type: "ship_progress", batchId: "b1", orderId: 3, result: "success" },
      { type: "ship_done", batchId: "b1", ok: 1, failed: 0, skipped: 0 },
    ]);
    expect(state.tasks).toEqual([]);
  });

  it("打印进度累加到进行中的打印任务，print_done 后移除", () => {
    const mid = run([
      { type: "print_progress", jobId: 1, result: "success" },
      { type: "print_progress", jobId: 2, result: "manual" },
    ]);
    expect(mid.tasks).toHaveLength(1);
    expect(mid.tasks[0]).toMatchObject({ kind: "print", title: "打印面单", counts: { ok: 1, waiting: 1 } });
    const done = applyProgressEvent(mid, { type: "print_done", ok: 1, failed: 0, manual: 1, skipped: 0 });
    expect(done.tasks).toEqual([]);
  });

  it("没有对应进行中任务的 done 事件不改状态", () => {
    const state = run([labelProgress("p1", 1)]);
    expect(applyProgressEvent(state, { type: "ship_done", batchId: "x", ok: 0, failed: 0, skipped: 0 })).toBe(state);
  });

  it(`最多保留 ${PROGRESS_LIMIT} 条，丢最早的`, () => {
    const events = Array.from({ length: PROGRESS_LIMIT + 1 }, (_, i) => labelProgress(`p${i}`, i));
    const state = run(events);
    expect(state.tasks).toHaveLength(PROGRESS_LIMIT);
    expect(state.tasks.some((t) => t.id === "label:p0")).toBe(false);
  });

  it("countsText 只列非零项，没有结果时显示等待", () => {
    const state = run([labelProgress("p1", 1), labelProgress("p1", 2, "verifying")]);
    expect(countsText(state.tasks[0])).toBe("成功 1，待核实 1");
    const empty = run([{ type: "print_progress", jobId: 1, result: "unknown" }]);
    expect(countsText(empty.tasks[0])).toBe("等待结果");
  });
});

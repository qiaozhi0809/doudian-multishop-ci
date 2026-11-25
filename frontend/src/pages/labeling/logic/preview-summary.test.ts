import {
  applyDone,
  executePath,
  initialProgress,
  mergeProgress,
  previewPath,
  previewTotals,
  type PreviewResponse,
  type ProgressEvent,
} from "./preview-summary";

function event(overrides: Partial<ProgressEvent>): ProgressEvent {
  return {
    preview_id: "p1",
    mode: "obtain",
    order_id: 1,
    order_no: "o1",
    result: "success",
    tracking_no: null,
    reason: null,
    ...overrides,
  };
}

describe("label progress", () => {
  it("逐单事件累计计数，同一订单以最后一次为准", () => {
    let state = initialProgress();
    state = mergeProgress(state, event({ order_id: 1, result: "failed", reason: "超区" }));
    state = mergeProgress(state, event({ order_id: 2, result: "verifying" }));
    expect([state.ok, state.failed, state.verifying, state.skipped]).toEqual([0, 1, 1, 0]);

    state = mergeProgress(state, event({ order_id: 1, result: "success", tracking_no: "T1" }));
    expect([state.ok, state.failed, state.verifying]).toEqual([1, 0, 1]);
    expect(state.rows[1].trackingNo).toBe("T1");
  });

  it("结束事件以服务端计数为准", () => {
    const done = applyDone(initialProgress(), {
      preview_id: "p1",
      mode: "obtain",
      ok: 3,
      failed: 1,
      verifying: 2,
      skipped: 0,
    });
    expect(done.done).toBe(true);
    expect([done.ok, done.failed, done.verifying, done.skipped]).toEqual([3, 1, 2, 0]);
  });

  it("预览汇总与接口路径", () => {
    const preview = {
      preview_id: "p1",
      mode: "obtain",
      shops: [{}, {}],
      blocked: [{}],
      shop_errors: [],
      total_ready: 5,
      total_blocked: 1,
      dry_run: false,
    } as unknown as PreviewResponse;
    expect(previewTotals(preview)).toEqual({ ready: 5, blocked: 1, shops: 2 });
    expect(previewPath("obtain")).toBe("/api/labels/preview");
    expect(previewPath("fetch_and_ship")).toBe("/api/labels/fetch-and-ship/preview");
    expect(previewPath("void")).toBe("/api/labels/void/preview");
    expect(executePath("obtain")).toBe("/api/labels/execute");
    expect(executePath("fetch_and_ship")).toBe("/api/labels/fetch-and-ship/execute");
    expect(executePath("void")).toBe("/api/labels/void/execute");
  });
});

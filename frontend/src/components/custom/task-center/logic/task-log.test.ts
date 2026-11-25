import {
  TASK_LIMIT,
  applyTaskEvent,
  countsText,
  emptyTaskCenter,
  runningCount,
  statusText,
  type TaskEvent,
} from "./task-log";

const run = (events: TaskEvent[]) => events.reduce(applyTaskEvent, emptyTaskCenter());

describe("任务状态机", () => {
  it("取号：计划事件建任务并计数，完成事件以服务端汇总收尾", () => {
    let state = run([
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: 1, result: "success" },
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: 2, result: "failed" },
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: 3, result: "verifying" },
    ]);
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0]).toMatchObject({
      id: "label:p1",
      title: "打单",
      status: "running",
      counts: { ok: 1, failed: 1, waiting: 1, skipped: 0 },
    });
    expect(runningCount(state.tasks)).toBe(1);

    state = applyTaskEvent(state, {
      type: "label_done",
      previewId: "p1",
      ok: 3,
      failed: 1,
      verifying: 2,
      skipped: 4,
    });
    expect(state.tasks[0]).toMatchObject({
      status: "done",
      counts: { ok: 3, failed: 1, waiting: 2, skipped: 4 },
    });
    expect(runningCount(state.tasks)).toBe(0);
  });

  it("同一订单的重试事件不重复计数", () => {
    const state = run([
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: 7, result: "failed" },
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: 7, result: "success" },
      { type: "ship_progress", batchId: "b1", orderId: 8, result: "success" },
      { type: "ship_progress", batchId: "b1", orderId: 8, result: "failed" },
    ]);
    expect(state.tasks.find((task) => task.id === "label:p1")?.counts).toMatchObject({
      ok: 0,
      failed: 1,
    });
    expect(state.tasks.find((task) => task.id === "ship:b1")?.counts).toMatchObject({
      ok: 1,
      failed: 0,
    });
  });

  it("三种打单模式各有标题，未知模式回落到「打单」", () => {
    const titles = ["obtain", "fetch_and_ship", "void", "other"].map((mode, index) => {
      const state = run([{ type: "label_progress", previewId: `p${index}`, mode, orderId: 1, result: "success" }]);
      return state.tasks[0].title;
    });
    expect(titles).toEqual(["打单", "打单并发货", "作废面单", "打单"]);
  });

  it("没有订单号的事件不建任务", () => {
    const state = run([
      { type: "label_progress", previewId: "p1", mode: "obtain", orderId: null, result: "success" },
      { type: "ship_progress", batchId: "b1", orderId: null, result: "success" },
    ]);
    expect(state.tasks).toEqual([]);
  });

  it("未见过进度事件的完成事件被忽略", () => {
    const state = run([
      { type: "label_done", previewId: "p1", ok: 1, failed: 0, verifying: 0, skipped: 0 },
      { type: "ship_done", batchId: "b1", ok: 1, failed: 0, skipped: 0 },
      { type: "print_done", ok: 1, failed: 0, manual: 0, skipped: 0 },
    ]);
    expect(state.tasks).toEqual([]);
  });

  it("发货：成功、失败、跳过分别计数", () => {
    let state = run([
      { type: "ship_progress", batchId: "b1", orderId: 1, result: "success" },
      { type: "ship_progress", batchId: "b1", orderId: 2, result: "skipped" },
    ]);
    state = applyTaskEvent(state, { type: "ship_done", batchId: "b1", ok: 1, failed: 0, skipped: 1 });
    expect(state.tasks[0]).toMatchObject({
      id: "ship:b1",
      title: "发货",
      status: "done",
      counts: { ok: 1, failed: 0, waiting: 0, skipped: 1 },
    });
  });

  it("打印没有批次 id：连续事件归入同一个进行中任务，结束后下一次打印新建任务", () => {
    let state = run([
      { type: "print_progress", jobId: 11, result: "success" },
      { type: "print_progress", jobId: 11, result: "success" },
      { type: "print_progress", jobId: 12, result: "manual" },
    ]);
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0]).toMatchObject({
      id: "print:1",
      title: "打印面单",
      status: "running",
      counts: { ok: 1, failed: 0, waiting: 1, skipped: 0 },
    });

    state = applyTaskEvent(state, { type: "print_done", ok: 2, failed: 0, manual: 1, skipped: 0 });
    expect(state.tasks[0]).toMatchObject({ status: "done", counts: { ok: 2, waiting: 1 } });

    state = applyTaskEvent(state, { type: "print_progress", jobId: 13, result: "failed" });
    expect(state.tasks).toHaveLength(2);
    expect(state.tasks[0]).toMatchObject({ id: "print:2", status: "running", counts: { failed: 1 } });
  });

  it("清除已完成只保留进行中的任务；单个任务可单独清除", () => {
    let state = run([
      { type: "label_progress", previewId: "a", mode: "obtain", orderId: 1, result: "success" },
      { type: "label_done", previewId: "a", ok: 1, failed: 0, verifying: 0, skipped: 0 },
      { type: "ship_progress", batchId: "b", orderId: 2, result: "success" },
    ]);
    expect(state.tasks).toHaveLength(2);
    state = applyTaskEvent(state, { type: "clear_finished" });
    expect(state.tasks.map((task) => task.id)).toEqual(["ship:b"]);
    state = applyTaskEvent(state, { type: "dismiss", id: "ship:b" });
    expect(state.tasks).toEqual([]);
  });

  it(`最多保留 ${TASK_LIMIT} 条：先丢最早的已完成任务，其次丢最早的`, () => {
    let state = emptyTaskCenter();
    for (let i = 0; i < 10; i++) {
      state = applyTaskEvent(state, {
        type: "label_progress",
        previewId: `p${i}`,
        mode: "obtain",
        orderId: i,
        result: "success",
      });
    }
    expect(state.tasks).toHaveLength(TASK_LIMIT);
    expect(state.tasks[0].id).toBe("label:p9");
    expect(state.tasks.some((task) => task.id === "label:p0")).toBe(false);

    state = applyTaskEvent(state, {
      type: "label_done",
      previewId: "p5",
      ok: 1,
      failed: 0,
      verifying: 0,
      skipped: 0,
    });
    state = applyTaskEvent(state, {
      type: "label_progress",
      previewId: "p10",
      mode: "obtain",
      orderId: 10,
      result: "success",
    });
    expect(state.tasks).toHaveLength(TASK_LIMIT);
    expect(state.tasks.some((task) => task.id === "label:p5")).toBe(false);
  });
});

describe("任务文案", () => {
  const task = (over: Partial<Parameters<typeof countsText>[0]>) => ({
    id: "t",
    kind: "label" as const,
    title: "取号",
    status: "running" as const,
    counts: { ok: 0, failed: 0, waiting: 0, skipped: 0 },
    seen: [],
    ...over,
  });

  it("摘要只列非零项，等待中还没结果时提示等待", () => {
    expect(countsText(task({}))).toBe("等待结果");
    expect(countsText(task({ counts: { ok: 2, failed: 1, waiting: 3, skipped: 1 } }))).toBe(
      "成功 2，失败 1，待核实 3，跳过 1",
    );
    expect(countsText(task({ kind: "print", counts: { ok: 0, failed: 0, waiting: 2, skipped: 0 } }))).toBe(
      "需补打 2",
    );
    expect(countsText(task({ status: "done", counts: { ok: 1, failed: 0, waiting: 0, skipped: 0 } }))).toBe(
      "成功 1",
    );
  });

  it("状态文案：进行中；完成；完成但有失败", () => {
    expect(statusText(task({}))).toBe("进行中");
    expect(statusText(task({ status: "done", counts: { ok: 1, failed: 0, waiting: 0, skipped: 0 } }))).toBe("完成");
    expect(statusText(task({ status: "done", counts: { ok: 0, failed: 1, waiting: 0, skipped: 0 } }))).toBe(
      "完成，有失败",
    );
  });

  it("临近发货超时：生成提醒任务，重复事件更新计数，清零后移除", () => {
    let state = run([{ type: "deadline_warning", count: 3, warnHours: 6 }]);
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0]).toMatchObject({
      id: "deadline",
      kind: "deadline",
      status: "alert",
      counts: { ok: 0, failed: 0, waiting: 3, skipped: 0 },
    });
    expect(state.tasks[0].title).toContain("6 小时");
    expect(countsText(state.tasks[0])).toBe("临近超时 3");
    expect(statusText(state.tasks[0])).toBe("提醒");
    expect(runningCount(state.tasks)).toBe(0);

    state = applyTaskEvent(state, { type: "deadline_warning", count: 2, warnHours: 6 });
    expect(state.tasks).toHaveLength(1);
    expect(state.tasks[0].counts.waiting).toBe(2);

    state = applyTaskEvent(state, { type: "deadline_warning", count: 0, warnHours: 6 });
    expect(state.tasks).toHaveLength(0);
  });
});

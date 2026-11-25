import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskCenter } from "./task-center";
import type { TaskItem } from "../logic/task-log";

const makeTask = (over: Partial<TaskItem> = {}): TaskItem => ({
  id: "label:1",
  kind: "label",
  title: "打单",
  status: "running",
  counts: { ok: 2, failed: 1, waiting: 0, skipped: 0 },
  seen: [],
  ...over,
});

const noop = () => {};

describe("任务中心", () => {
  it("有进行中任务时按钮显示数量，展开后列出进度", async () => {
    render(<TaskCenter tasks={[makeTask()]} runningCount={1} onDismiss={noop} onClearFinished={noop} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "任务中心，1 个进行中" }));
    expect(await screen.findByText("打单")).toBeInTheDocument();
    expect(screen.getByText("进行中")).toBeInTheDocument();
    expect(screen.getByText("成功 2，失败 1")).toBeInTheDocument();
  });

  it("已完成任务可单独清除，也可一键清除全部已完成", async () => {
    const onDismiss = vi.fn();
    const onClearFinished = vi.fn();
    const done = makeTask({ id: "label:2", status: "done", counts: { ok: 1, failed: 0, waiting: 0, skipped: 0 } });
    render(<TaskCenter tasks={[done]} runningCount={0} onDismiss={onDismiss} onClearFinished={onClearFinished} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "任务中心" }));
    expect(await screen.findByText("完成")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "清除打单任务" }));
    expect(onDismiss).toHaveBeenCalledWith("label:2");
    await user.click(screen.getByRole("button", { name: "清除已完成" }));
    expect(onClearFinished).toHaveBeenCalled();
  });

  it("没有任务时给出说明", async () => {
    render(<TaskCenter tasks={[]} runningCount={0} onDismiss={noop} onClearFinished={noop} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "任务中心" }));
    expect(await screen.findByText(/没有进行中的任务/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "清除已完成" })).not.toBeInTheDocument();
  });

  it("失败的任务用警告色标记", async () => {
    const done = makeTask({ status: "done", counts: { ok: 1, failed: 2, waiting: 0, skipped: 0 } });
    render(<TaskCenter tasks={[done]} runningCount={0} onDismiss={noop} onClearFinished={noop} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "任务中心" }));
    expect(await screen.findByText("完成，有失败")).toBeInTheDocument();
    expect(screen.getByText("成功 1，失败 2")).toBeInTheDocument();
  });
});

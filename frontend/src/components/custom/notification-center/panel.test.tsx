import { act, screen, waitFor, within } from "@testing-library/react";
import { progressStore } from "./hooks/use-progress";
import { called, item, openPanel, setup, setupNotificationTests, shop } from "./test-harness";

setupNotificationTests();

describe("通知面板", () => {
  it("依次为进行中、待处理、通知列表；未读加粗", async () => {
    progressStore.publish({ type: "ship_progress", batchId: "b1", orderId: 1, result: "success" });
    setup({
      strongOpen: [shop(1, ["login_expired"], "/shops?shop=1")],
      items: [
        item({ id: 2, kind: "login_expired", level: "strong", state_key: "login:1", title: "示例店1 登录失效" }),
        item({ id: 1 }),
        item({ id: 3, level: "weak", kind: "sync_done", title: "示例店1 订单同步完成", read_at: "2026-11-25T09:00:00" }),
      ],
    });
    const { panel } = await openPanel();
    const titles = within(panel).getAllByRole("heading").map((h) => h.textContent);
    expect(titles).toEqual(["通知", "进行中", "待处理", "最近"]);
    const ongoing = within(panel).getByRole("region", { name: "进行中" });
    expect(ongoing).toHaveTextContent("发货");
    expect(ongoing).toHaveTextContent("成功 1");
    expect(within(within(panel).getByRole("region", { name: "待处理" })).getByRole("group", { name: "示例店1" })).toHaveTextContent("示例店1：登录失效");
    const recent = within(panel).getByRole("region", { name: "最近" });
    expect(within(recent).queryByText("示例店1 登录失效")).not.toBeInTheDocument();
    expect(within(recent).getByText("示例店 新增 2 单待发货").closest("button")).toHaveAttribute("data-unread", "true");
    expect(within(recent).getByText("示例店1 订单同步完成").closest("button")).not.toHaveAttribute("data-unread");
  });

  it("待处理列出摘要里全部未解决的店（不受列表分页影响），点击跳转", async () => {
    setup({ items: [item()], strongOpen: [1, 2, 3, 4].map((id) => shop(id, ["risk_paused"], `/shops?shop=${id}`)) });
    const { user, panel } = await openPanel();
    const open = within(panel).getByRole("region", { name: "待处理" });
    expect(within(open).getAllByRole("button")).toHaveLength(4);
    await user.click(within(within(open).getByRole("group", { name: "示例店3" })).getByRole("button", { name: "风控暂停" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/shops?shop=3");
    expect(screen.queryByRole("dialog", { name: "通知" })).not.toBeInTheDocument();
  });

  it("点击通知标为已读并跳转", async () => {
    const fetch = setup({ items: [item()] });
    const { user, panel } = await openPanel();
    await user.click(within(panel).getByText("示例店 新增 2 单待发货"));
    expect(screen.getByTestId("where")).toHaveTextContent("/orders?shops=1");
    await waitFor(() => expect(called(fetch, "/api/notifications/1/read")).toBe(true));
  });

  it("全部已读", async () => {
    const fetch = setup({ items: [item()] });
    const { user, panel } = await openPanel();
    await user.click(within(panel).getByRole("button", { name: "全部已读" }));
    await waitFor(() => expect(called(fetch, "/api/notifications/read-all")).toBe(true));
  });

  it("「全部 / 未读」分段切换：选未读带 unread 参数，可切回全部", async () => {
    const fetch = setup({ items: [item()] });
    const { user, panel } = await openPanel();
    const filter = within(panel).getByRole("group", { name: "通知筛选" });
    const all = within(filter).getByRole("button", { name: "全部" });
    const unreadOnly = within(filter).getByRole("button", { name: "未读" });
    expect(all).toHaveAttribute("aria-pressed", "true");
    await user.click(unreadOnly);
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).includes("unread=true"))).toBe(true));
    expect(unreadOnly).toHaveAttribute("aria-pressed", "true");
    await user.click(within(within(panel).getByRole("group", { name: "通知筛选" })).getByRole("button", { name: "全部" }));
    expect(within(panel).getByRole("button", { name: "全部" })).toHaveAttribute("aria-pressed", "true");
    expect(within(panel).queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("提示音是开关：开着为响，关掉存本地", async () => {
    setup();
    const { user, panel } = await openPanel();
    const sound = within(panel).getByRole("switch", { name: "提示音" });
    expect(sound).toBeChecked();
    await user.click(sound);
    expect(sound).not.toBeChecked();
    expect(localStorage.getItem("notify.muted")).toBe("1");
    await user.click(sound);
    expect(sound).toBeChecked();
    expect(localStorage.getItem("notify.muted")).toBe("0");
  });

  it("本地存的是静音时，提示音开关为关", async () => {
    localStorage.setItem("notify.muted", "1");
    setup();
    const { panel } = await openPanel();
    expect(within(panel).getByRole("switch", { name: "提示音" })).not.toBeChecked();
  });

  it("筛选与全部已读在最近区块里，分页单独一行", async () => {
    setup({ items: [item()], total: 41 });
    const { panel } = await openPanel();
    const pager = await within(panel).findByRole("navigation", { name: "通知分页" });
    const recent = within(panel).getByRole("region", { name: "最近" });
    const markAll = within(recent).getByRole("button", { name: "全部已读" });
    expect(within(recent).getByRole("group", { name: "通知筛选" })).toBeInTheDocument();
    expect(recent).not.toContainElement(pager);
    expect(pager.parentElement).not.toContainElement(markAll);
  });

  it("没有未读时全部已读禁用，聚焦说明原因", async () => {
    setup({ items: [item({ read_at: "2026-11-25T09:00:00" })], unread: 0 });
    const { panel } = await openPanel();
    const markAll = within(panel).getByRole("button", { name: "全部已读" });
    expect(markAll).toBeDisabled();
    act(() => markAll.parentElement!.focus());
    expect(await screen.findByRole("tooltip")).toHaveTextContent("没有未读通知");
  });

  it("没有通知时只写暂无通知，不显示进行中与待处理", async () => {
    setup();
    const { panel } = await openPanel();
    expect(await within(panel).findByText("暂无通知")).toHaveClass("panel-empty");
    expect(within(panel).queryByRole("region", { name: "进行中" })).not.toBeInTheDocument();
    expect(within(panel).queryByRole("region", { name: "待处理" })).not.toBeInTheDocument();
  });
});

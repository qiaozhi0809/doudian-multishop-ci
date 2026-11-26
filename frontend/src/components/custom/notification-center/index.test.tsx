import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { item, setup, setupNotificationTests, shop } from "./test-harness";

setupNotificationTests();

describe("顶部强提醒横条", () => {
  it("两店有问题：一店一行，同店问题写在一起", async () => {
    setup({ strongOpen: [shop(1, ["login_expired", "egress_unreachable"], "/shops?shop=1"), shop(2, ["risk_paused"], "/shops?shop=2")] });
    const banner = await screen.findByRole("region", { name: "需要处理的店铺" });
    const rows = within(banner).getAllByRole("group");
    expect(rows.map((r) => r.textContent)).toEqual(["示例店1：登录失效、出口不通", "示例店2：风控暂停"]);
    expect(within(rows[0]).getAllByRole("button").map((b) => b.textContent)).toEqual(["登录失效", "出口不通"]);
    expect(within(banner).queryByRole("button", { name: /关闭/ })).not.toBeInTheDocument();
  });

  it("每个问题跳各自的链接", async () => {
    setup({
      strongOpen: [shop(2, ["login_expired", "ship_deadline"], "/shops?shop=2", { ship_deadline: "/orders?quick=ship_delay&shops=2" })],
    });
    const row = await screen.findByRole("group", { name: "示例店2" });
    await userEvent.setup().click(within(row).getByRole("button", { name: "临近发货超时" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/orders?quick=ship_delay&shops=2");
  });

  it("四店有问题：合并为一行，点击打开通知面板", async () => {
    setup({ strongOpen: [1, 2, 3, 4].map((id) => shop(id, ["login_expired"])) });
    const banner = await screen.findByRole("region", { name: "需要处理的店铺" });
    expect(within(banner).getAllByRole("button")).toHaveLength(1);
    await userEvent.setup().click(within(banner).getByRole("button", { name: "4 家店需要处理" }));
    expect(await screen.findByRole("dialog", { name: "通知" })).toBeInTheDocument();
  });

  it("没有未解决的强提醒时不显示横条", async () => {
    setup();
    await screen.findByRole("button", { name: "通知" });
    expect(screen.queryByRole("region", { name: "需要处理的店铺" })).not.toBeInTheDocument();
  });
});

describe("铃铛", () => {
  it("纯图标按钮，显示未读数；有未解决的强提醒时徽标为红色", async () => {
    setup({ items: [item()], unread: 3, strongOpen: [shop(1, ["login_expired"])] });
    const bell = await screen.findByRole("button", { name: "通知" });
    await waitFor(() => expect(screen.getByTestId("notification-count")).toHaveTextContent("3"));
    expect(screen.getByTestId("notification-count")).toHaveAttribute("data-urgent", "true");
    expect(bell).toHaveAccessibleDescription("3 条未读，有店铺需要处理");
  });

  it("点铃铛时（权限未决定）申请一次系统通知权限", async () => {
    const requestPermission = vi.fn().mockResolvedValue("granted");
    vi.stubGlobal("Notification", { permission: "default", requestPermission });
    try {
      setup({ items: [item()] });
      const user = userEvent.setup();
      expect(requestPermission).not.toHaveBeenCalled();
      await user.click(await screen.findByRole("button", { name: "通知" }));
      expect(requestPermission).toHaveBeenCalledTimes(1);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("没有未读时不显示数字", async () => {
    setup({ items: [item({ read_at: "2026-11-25T09:00:00" })], unread: 0 });
    await screen.findByRole("button", { name: "通知" });
    expect(screen.queryByTestId("notification-count")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "通知" })).toHaveAccessibleDescription("");
  });
});

describe("右下角弹窗", () => {
  it("状态类强提醒不弹窗，但响提示音（横条已常驻显示）", async () => {
    const play = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("Audio", vi.fn(() => ({ play })));
    try {
      setup();
      await screen.findByRole("button", { name: "通知" });
      const strongItem = item({ id: 12, level: "strong", kind: "login_expired", shop_id: 1, state_key: "login:1", title: "示例店 登录失效" });
      act(() => FakeEventSource.latest().emit("notification", { action: "created", item: strongItem, alert: true }));
      await waitFor(() => expect(play).toHaveBeenCalledTimes(1));
      expect(within(screen.getByLabelText("操作提示")).queryByText("示例店 登录失效")).not.toBeInTheDocument();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("未读时又来新售后（合并后数量变多）：再弹一次并响提示音", async () => {
    const play = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("Audio", vi.fn(() => ({ play })));
    try {
      setup();
      await screen.findByRole("button", { name: "通知" });
      const first = item({ id: 20, kind: "new_aftersale", level: "strong", title: "示例店 新增 1 个售后", count: 1 });
      act(() => FakeEventSource.latest().emit("notification", { action: "created", item: first, alert: true }));
      const toasts = screen.getByLabelText("操作提示");
      expect(within(toasts).getByText("示例店 新增 1 个售后")).toBeInTheDocument();
      const merged = { ...first, title: "示例店 新增 2 个售后", count: 2 };
      act(() => FakeEventSource.latest().emit("notification", { action: "updated", item: merged, alert: true }));
      expect(within(toasts).getByText("示例店 新增 2 个售后")).toBeInTheDocument();
      expect(within(toasts).queryByText("示例店 新增 1 个售后")).not.toBeInTheDocument();
      await waitFor(() => expect(play).toHaveBeenCalledTimes(2));
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("中档 5 秒后消失，强档不消失，弱档不弹", async () => {
    setup();
    await screen.findByRole("button", { name: "通知" });
    vi.useFakeTimers();
    act(() => {
      FakeEventSource.latest().emit("notification", { action: "created", item: item({ id: 11, title: "示例店 新增 1 单待发货" }), alert: true });
      FakeEventSource.latest().emit("notification", {
        action: "created", item: item({ id: 12, level: "strong", kind: "new_aftersale", title: "示例店 新增 1 个售后" }), alert: true,
      });
      FakeEventSource.latest().emit("notification", { action: "created", item: item({ id: 13, level: "weak", title: "示例店 订单同步完成" }), alert: true });
    });
    const toasts = screen.getByLabelText("操作提示");
    expect(within(toasts).getByText("示例店 新增 1 单待发货")).toBeInTheDocument();
    expect(within(toasts).getByText("示例店 新增 1 个售后")).toBeInTheDocument();
    expect(within(toasts).queryByText("示例店 订单同步完成")).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(5100));
    expect(within(toasts).queryByText("示例店 新增 1 单待发货")).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(60_000));
    expect(within(toasts).getByText("示例店 新增 1 个售后")).toBeInTheDocument();
  });
});

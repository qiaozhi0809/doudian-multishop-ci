import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { NoticeProvider } from "@/components/custom/notice/notice";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { progressStore } from "./hooks/use-progress";
import type { NotificationItem, StrongOpenShop } from "./logic/notification-view";
import { NotificationBanner, NotificationBell, NotificationCenterProvider } from "./index";

const item = (over: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 1, kind: "new_order", level: "medium", shop_id: 1, state_key: null, title: "示例店 新增 2 单待发货",
  body: null, link: "/orders?shops=1", count: 2, read_at: null, resolved_at: null,
  created_at: "2026-11-25T08:00:00", updated_at: "2026-11-25T08:00:00", ...over,
});

/** links 给出每个问题各自的链接；不给时都用 link。 */
const shop = (
  id: number, kinds: StrongOpenShop["kinds"], link: string | null = null, links: Partial<Record<StrongOpenShop["kinds"][number], string>> = {},
): StrongOpenShop => ({
  shop_id: id, shop_name: `示例店${id}`, kinds, link, problems: kinds.map((kind) => ({ kind, link: links[kind] ?? link })),
});

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

interface Setup {
  items?: NotificationItem[];
  strongOpen?: StrongOpenShop[];
  unread?: number;
}

const live: { strongOpen: StrongOpenShop[] } = { strongOpen: [] };

function setup({ items = [], strongOpen = [], unread = items.filter((i) => !i.read_at).length }: Setup = {}) {
  live.strongOpen = strongOpen;
  const fetch = mockFetch({
    "GET /api/notifications": jsonResponse({ items, total: items.length, page: 1, page_size: 20 }),
    "GET /api/notifications/summary": () => jsonResponse({ unread, strong_open: live.strongOpen }),
    "POST /api/notifications/1/read": new Response(null, { status: 204 }),
    "POST /api/notifications/read-all": new Response(null, { status: 204 }),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <NoticeProvider>
          <NotificationCenterProvider>
            <NotificationBanner />
            <NotificationBell />
          </NotificationCenterProvider>
        </NoticeProvider>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

const called = (fetch: ReturnType<typeof mockFetch>, path: string) =>
  fetch.mock.calls.some(([url, init]) => String(url).split("?")[0] === path && init?.method === "POST");

let restore: () => void;
beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  progressStore.reset();
  restore = FakeEventSource.install();
});
afterEach(() => {
  vi.useRealTimers();
  restore();
});

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

describe("通知面板", () => {
  async function openPanel() {
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "通知" }));
    return { user, panel: await screen.findByRole("dialog", { name: "通知" }) };
  }

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

  it("只看未读切换带 unread 参数；提示音开关存本地", async () => {
    const fetch = setup({ items: [item()] });
    const { user, panel } = await openPanel();
    await user.click(within(panel).getByRole("checkbox", { name: "只看未读" }));
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => String(url).includes("unread=true"))).toBe(true));
    const sound = within(panel).getByRole("checkbox", { name: "提示音" });
    expect(sound).toBeChecked();
    await user.click(sound);
    expect(localStorage.getItem("notify.muted")).toBe("1");
  });

  it("没有通知时只写暂无通知，不显示进行中与待处理", async () => {
    setup();
    const { panel } = await openPanel();
    expect(await within(panel).findByText("暂无通知")).toBeInTheDocument();
    expect(within(panel).queryByRole("region", { name: "进行中" })).not.toBeInTheDocument();
    expect(within(panel).queryByRole("region", { name: "待处理" })).not.toBeInTheDocument();
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

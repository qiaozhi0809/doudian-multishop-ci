import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { RequireAuth } from "@/pages/auth/require-auth";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { AppShell } from "./index";

const IN = { setup_required: false, logged_in: true, username: "admin" };

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

function renderShell(path: string, extraRoutes: Record<string, ReturnType<typeof jsonResponse> | (() => Response)> = {}, shops = [makeShop()]) {
  mockFetch({
    "GET /api/auth/status": jsonResponse(IN),
    "GET /api/shops": jsonResponse(shops),
    ...extraRoutes,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<h1>登录页</h1>} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route path="/orders" element={<p>订单内容</p>} />
              <Route path="/shops" element={<p>店铺内容</p>} />
            </Route>
          </Route>
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return client;
}

let restoreEvents: () => void;
beforeEach(() => {
  localStorage.clear();
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  localStorage.clear();
});

describe("App Shell", () => {
  it("标题行显示页面标题，侧边栏有全部订单与店铺管理", async () => {
    renderShell("/orders");
    expect(await screen.findByRole("heading", { level: 1, name: "全部订单" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "主导航" });
    expect(within(nav).getByRole("link", { name: "全部订单" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "店铺管理" })).toBeInTheDocument();
    expect(screen.getByText("订单内容")).toBeInTheDocument();
  });

  it("挂载 useEvents：建立 SSE 连接", async () => {
    renderShell("/orders");
    await screen.findByRole("heading", { name: "全部订单" });
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("导航为分组结构，概览 / 打单发货 / 发货异常入口都在", async () => {
    renderShell("/orders");
    const nav = await screen.findByRole("navigation", { name: "主导航" });
    expect(within(nav).getByRole("link", { name: "概览" })).toHaveAttribute("href", "/dashboard");
    expect(within(nav).getByRole("link", { name: "打单发货" })).toHaveAttribute("href", "/labeling");
    expect(within(nav).getByRole("link", { name: "发货异常" })).toHaveAttribute("href", "/reconcile");
    const group = within(nav).getByRole("group", { name: "订单" });
    expect(within(group).getByRole("link", { name: "全部订单" })).toHaveAttribute("aria-current", "page");
  });

  it("进外壳就预取各页指标卡的数（订单 / 售后 / 商品计数、库存与资金汇总）", async () => {
    renderShell("/orders");
    await screen.findByRole("heading", { level: 1, name: "全部订单" });
    const called = () => (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.map(([u]) => String(u).split("?")[0]);
    await waitFor(() =>
      expect(called()).toEqual(
        expect.arrayContaining([
          "/api/orders/counts",
          "/api/aftersale/counts",
          "/api/catalog/products/counts",
          "/api/catalog/stock/summary",
          "/api/fund/summary",
        ]),
      ),
    );
  });

  it("侧栏常驻任务中心", async () => {
    renderShell("/orders");
    expect(await screen.findByRole("button", { name: "任务中心" })).toBeInTheDocument();
  });

  it("会话掉线时可在顶栏一键重登", async () => {
    renderShell(
      "/orders",
      { "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) },
      [makeShop(), makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired" })],
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /1 家店需处理/ }));
    await user.click(await screen.findByRole("button", { name: "重新登录" }));
    expect(await screen.findByText("等待扫码")).toBeInTheDocument();
    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 2, status: "active" }));
    await waitFor(() => expect(screen.queryByText("等待扫码")).not.toBeInTheDocument());
  });

  it("重登失败的原因显示在店铺这一行", async () => {
    renderShell(
      "/orders",
      { "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) },
      [makeShop(), makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired" })],
    );
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /1 家店需处理/ }));
    await user.click(await screen.findByRole("button", { name: "重新登录" }));
    act(() =>
      FakeEventSource.latest().emit("shop_login_failed", { shop_id: 2, reason: "请先检查出口" }),
    );
    expect(await screen.findByText("请先检查出口")).toBeInTheDocument();
  });

  it("导航链接带着当前店铺筛选", async () => {
    renderShell("/orders?shops=1&page=3");
    const nav = await screen.findByRole("navigation", { name: "主导航" });
    expect(within(nav).getByRole("link", { name: "店铺管理" })).toHaveAttribute("href", "/shops?shops=1");
  });

  it("店铺都正常时显示店铺正常", async () => {
    renderShell("/orders");
    expect(await screen.findByText("店铺正常")).toBeInTheDocument();
  });

  it("没有店铺时显示还没有店铺，并链接到店铺页", async () => {
    renderShell("/orders", {}, []);
    const link = await screen.findByRole("link", { name: "还没有店铺" });
    expect(link).toHaveAttribute("href", "/shops");
    expect(screen.queryByText("店铺正常")).not.toBeInTheDocument();
  });

  it("有店铺需处理时显示数量，弹层列出店铺与最严重的问题", async () => {
    renderShell("/orders", {}, [
      makeShop(),
      makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired", egress_status: "duplicate" }),
    ]);
    const trigger = await screen.findByRole("button", { name: /1 家店需处理/ });
    await userEvent.setup().click(trigger);
    expect(await screen.findByText("店铺乙")).toBeInTheDocument();
    expect(screen.getByText("需重新登录")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "前往店铺页" })).toHaveAttribute("href", "/shops");
  });

  it("即将过期时显示警告数量", async () => {
    renderShell("/orders", {}, [makeShop({ health: "expiring" })]);
    expect(await screen.findByRole("button", { name: /1 家店即将到期/ })).toBeInTheDocument();
  });

  it("风控暂停、出口异常的店铺也算需处理，不显示店铺正常", async () => {
    renderShell("/orders", {}, [
      makeShop({ id: 1, name: "甲", paused_reason: "risk_blocked:1" }),
      makeShop({ id: 2, name: "乙", egress_status: "unreachable" }),
    ]);
    expect(await screen.findByRole("button", { name: /2 家店需处理/ })).toBeInTheDocument();
    expect(screen.queryByText("店铺正常")).not.toBeInTheDocument();
  });

  it("店铺列表读取失败时健康指示显示出错并可重试", async () => {
    renderShell("/orders", { "GET /api/shops": errorResponse(500, "Internal", "boom") });
    expect(await screen.findByRole("button", { name: "重新读取店铺" })).toBeInTheDocument();
  });

  it("店铺筛选写入 URL，并在切换时回到第 1 页", async () => {
    renderShell("/orders?page=3", {}, [makeShop(), makeShop({ id: 2, name: "店铺乙" })]);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /店铺筛选/ }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: "店铺乙" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/orders?shops=2"));
    expect(screen.getByRole("button", { name: "店铺筛选，店铺乙", hidden: true })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitemcheckbox", { name: "全部店铺" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(/^\/orders$/));
  });

  it("管理员菜单显示用户名，退出后回到登录页", async () => {
    const loggedIn = { value: true };
    renderShell("/orders", {
      "GET /api/auth/status": () => jsonResponse(loggedIn.value ? IN : { setup_required: false, logged_in: false, username: null }),
      "POST /api/auth/logout": () => {
        loggedIn.value = false;
        return new Response(null, { status: 204 });
      },
    });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /admin/ }));
    await user.click(await screen.findByRole("menuitem", { name: "退出登录" }));
    expect(await screen.findByRole("heading", { name: "登录页" })).toBeInTheDocument();
  });

  describe("修改密码对话框", () => {
    async function openDialog() {
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /admin/ }));
      await user.click(await screen.findByRole("menuitem", { name: "修改密码" }));
      const dialog = await screen.findByRole("dialog");
      return { user, dialog };
    }

    it("成功后就地提示", async () => {
      renderShell("/orders", { "POST /api/auth/password": new Response(null, { status: 204 }) });
      const { user, dialog } = await openDialog();
      await user.type(within(dialog).getByLabelText("原密码"), "old-password");
      await user.type(within(dialog).getByLabelText("新密码"), "new-password");
      await user.click(within(dialog).getByRole("button", { name: "修改密码" }));
      expect(await within(dialog).findByText("密码已修改，其他设备需要重新登录")).toBeInTheDocument();
    });

    it("失败显示原因，不用 toast", async () => {
      renderShell("/orders", { "POST /api/auth/password": errorResponse(500, "Internal", "boom") });
      const { user, dialog } = await openDialog();
      await user.type(within(dialog).getByLabelText("原密码"), "old-password");
      await user.type(within(dialog).getByLabelText("新密码"), "new-password");
      await user.click(within(dialog).getByRole("button", { name: "修改密码" }));
      expect(await within(dialog).findByText("修改密码失败，请稍后重试")).toBeInTheDocument();
    });

    it("新密码少于 8 位时提交前提示，不发请求", async () => {
      renderShell("/orders");
      const { user, dialog } = await openDialog();
      await user.type(within(dialog).getByLabelText("原密码"), "old-password");
      await user.type(within(dialog).getByLabelText("新密码"), "short");
      await user.click(within(dialog).getByRole("button", { name: "修改密码" }));
      expect(await within(dialog).findByText("密码至少 8 位")).toBeInTheDocument();
    });
  });
});

describe("演练模式横幅", () => {
  const INFO = {
    dry_run: true,
    version: "0.7.0",
    reconcile_daily: true,
    reconcile_hour: 3,
    backup_daily: true,
    backup_keep: 7,
    ship_deadline_warn_hours: 6,
  };

  it("dry_run 开启时顶部有醒目横幅", async () => {
    renderShell("/orders", { "GET /api/system/info": jsonResponse(INFO) });
    const banner = await screen.findByText(/演练模式/);
    expect(banner).toHaveTextContent("演练模式：取号、发货、打印、作废不会真的发送");
  });

  it("dry_run 关闭（或接口不可用）时没有横幅", async () => {
    renderShell("/orders", {
      "GET /api/system/info": jsonResponse({ ...INFO, dry_run: false }),
    });
    expect(await screen.findByRole("heading", { level: 1, name: "全部订单" })).toBeInTheDocument();
    expect(screen.queryByText(/演练模式/)).not.toBeInTheDocument();
  });
});

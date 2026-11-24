import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { RequireAuth } from "@/pages/auth/require-auth";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { AppShell } from "./index";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  constructor() {
    FakeEventSource.instances.push(this);
  }
  addEventListener() {}
  removeEventListener() {}
  close() {}
}

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

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => vi.unstubAllGlobals());

describe("App Shell", () => {
  it("顶栏显示页面标题，侧边栏有订单与店铺与设置", async () => {
    renderShell("/orders");
    expect(await screen.findByRole("heading", { level: 1, name: "订单" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "主导航" });
    expect(within(nav).getByRole("link", { name: "订单" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "店铺与设置" })).toBeInTheDocument();
    expect(screen.getByText("订单内容")).toBeInTheDocument();
  });

  it("挂载 useEvents：建立 SSE 连接", async () => {
    renderShell("/orders");
    await screen.findByRole("heading", { name: "订单" });
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("导航链接带着当前店铺筛选", async () => {
    renderShell("/orders?shops=1&page=3");
    const nav = await screen.findByRole("navigation", { name: "主导航" });
    expect(within(nav).getByRole("link", { name: "店铺与设置" })).toHaveAttribute("href", "/shops?shops=1");
  });

  it("健康正常时显示会话正常", async () => {
    renderShell("/orders");
    expect(await screen.findByText("会话正常")).toBeInTheDocument();
  });

  it("有店铺需重新登录时显示数量并给出处理入口", async () => {
    renderShell("/orders", {}, [
      makeShop(),
      makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired" }),
    ]);
    const trigger = await screen.findByRole("button", { name: /1 家需重新登录/ });
    await userEvent.setup().click(trigger);
    expect(await screen.findByText("店铺乙")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "前往店铺页" })).toHaveAttribute("href", "/shops");
  });

  it("即将过期时显示警告数量", async () => {
    renderShell("/orders", {}, [makeShop({ health: "expiring" })]);
    expect(await screen.findByRole("button", { name: /1 家即将过期/ })).toBeInTheDocument();
  });

  it("店铺列表读取失败时健康指示显示出错并可重试", async () => {
    renderShell("/orders", { "GET /api/shops": errorResponse(500, "Internal", "boom") });
    expect(await screen.findByRole("button", { name: "重新读取店铺" })).toBeInTheDocument();
  });

  it("店铺筛选写入 URL，并在切换时回到第 1 页", async () => {
    renderShell("/orders?page=3", {}, [makeShop(), makeShop({ id: 2, name: "店铺乙" })]);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /店铺筛选/ }));
    await user.click(await screen.findByRole("option", { name: "店铺乙" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/orders?shops=2"));
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
    await user.click(await screen.findByRole("menuitem", { name: "退出" }));
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

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import AuthPage from "./index";
import { RequireAuth } from "./require-auth";

const OUT = { setup_required: false, logged_in: false, username: null };
const IN = { setup_required: false, logged_in: true, username: "admin" };

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/setup" element={<AuthPage mode="setup" />} />
          <Route element={<RequireAuth />}>
            <Route path="/shops" element={<h1>店铺页</h1>} />
            <Route path="/orders" element={<h1>订单页</h1>} />
          </Route>
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("登录页", () => {
  it("未登录访问受保护页面跳到带 next 的登录页", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse(OUT) });
    renderApp("/shops?shops=1");
    expect(await screen.findByRole("button", { name: "登录" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login?next=%2Fshops%3Fshops%3D1");
  });

  it("需要初始化时进入创建管理员页", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse({ setup_required: true, logged_in: false, username: null }) });
    renderApp("/orders");
    expect(await screen.findByRole("button", { name: "创建账号" })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/setup");
  });

  it("login_wrong_password_no_redirect: 401 留在登录页并显示账号或密码错误", async () => {
    mockFetch({
      "GET /api/auth/status": jsonResponse(OUT),
      "POST /api/auth/login": errorResponse(401, "Unauthorized"),
    });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("账号"), "admin");
    await user.type(screen.getByLabelText("密码"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByText("账号或密码错误")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login");
  });

  it("locked_message: 423 显示锁定提示", async () => {
    mockFetch({
      "GET /api/auth/status": jsonResponse(OUT),
      "POST /api/auth/login": errorResponse(423, "Locked"),
    });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("账号"), "admin");
    await user.type(screen.getByLabelText("密码"), "password-1");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByText("尝试次数过多，请 5 分钟后再试")).toBeInTheDocument();
  });

  it("密码少于 8 位时提交前提示，不发请求", async () => {
    const fetchMock = mockFetch({ "GET /api/auth/status": jsonResponse(OUT) });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("账号"), "admin");
    await user.type(screen.getByLabelText("密码"), "1234567");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByText("密码至少 8 位")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("账号为空时提示，不发请求", async () => {
    const fetchMock = mockFetch({ "GET /api/auth/status": jsonResponse(OUT) });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("密码"), "password-1");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("请输入账号");
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  });

  it("登录成功后回到 next 指定的页面", async () => {
    let loggedIn = false;
    mockFetch({
      "GET /api/auth/status": () => jsonResponse(loggedIn ? IN : OUT),
      "POST /api/auth/login": () => {
        loggedIn = true;
        return jsonResponse(IN);
      },
    });
    renderApp("/login?next=%2Fshops%3Fshops%3D1");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("账号"), "admin");
    await user.type(screen.getByLabelText("密码"), "password-1");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByRole("heading", { name: "登录成功" })).toBeInTheDocument();
    // 完成动画播完才跳转
    expect(await screen.findByRole("heading", { name: "店铺页" }, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/shops?shops=1");
  });

  it("创建管理员成功后进入后台", async () => {
    let created = false;
    mockFetch({
      "GET /api/auth/status": () =>
        jsonResponse(created ? IN : { setup_required: true, logged_in: false, username: null }),
      "POST /api/auth/setup": () => {
        created = true;
        return jsonResponse(IN);
      },
    });
    renderApp("/setup");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("账号"), "admin");
    await user.type(screen.getByLabelText("密码"), "password-1");
    await user.click(screen.getByRole("button", { name: "创建账号" }));
    expect(await screen.findByRole("heading", { name: "管理员已创建" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "订单页" }, { timeout: 3000 })).toBeInTheDocument();
  });

  it("状态读取失败时给出出错提示与重试按钮", async () => {
    mockFetch({ "GET /api/auth/status": errorResponse(500, "Internal", "boom") });
    renderApp("/orders");
    expect(await screen.findByRole("button", { name: "重新加载" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("订单页")).not.toBeInTheDocument());
  });
});

import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { api, setUnauthorizedHandler } from "@/lib/api-client";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useAuth } from "./use-auth";
import { useUnauthorizedRedirect } from "./use-unauthorized-redirect";

const STATUS_OUT = { setup_required: false, logged_in: false, username: null };
const STATUS_IN = { setup_required: false, logged_in: true, username: "admin" };

function setup(initialPath = "/orders") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return { client, wrapper };
}

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

describe("useAuth", () => {
  it("读取登录状态", async () => {
    mockFetch({ "GET /api/auth/status": jsonResponse(STATUS_IN) });
    const { wrapper } = setup();
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toEqual(STATUS_IN));
  });

  it("login_wrong_password: 401 显示账号或密码错误，且不触发全局 401 处理", async () => {
    const unauthorized = vi.fn();
    setUnauthorizedHandler(unauthorized);
    mockFetch({
      "GET /api/auth/status": jsonResponse(STATUS_OUT),
      "POST /api/auth/login": errorResponse(401, "Unauthorized", "x"),
    });
    const { wrapper } = setup("/login");
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBeDefined());
    await act(() => result.current.login("admin", "wrong-password"));
    expect(result.current.error).toBe("账号或密码错误");
    expect(unauthorized).not.toHaveBeenCalled();
  });

  it("locked_message: 423 显示锁定提示", async () => {
    mockFetch({
      "GET /api/auth/status": jsonResponse(STATUS_OUT),
      "POST /api/auth/login": errorResponse(423, "Locked", "locked"),
    });
    const { wrapper } = setup("/login");
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBeDefined());
    await act(() => result.current.login("admin", "password-1"));
    expect(result.current.error).toBe("尝试次数过多，请 5 分钟后再试");
  });

  it("登录成功后重新读取状态并清除错误", async () => {
    let loggedIn = false;
    mockFetch({
      "GET /api/auth/status": () => jsonResponse(loggedIn ? STATUS_IN : STATUS_OUT),
      "POST /api/auth/login": () => {
        loggedIn = true;
        return jsonResponse(STATUS_IN);
      },
    });
    const { wrapper } = setup("/login");
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status?.logged_in).toBe(false));
    await act(() => result.current.login("admin", "password-1"));
    await waitFor(() => expect(result.current.status?.logged_in).toBe(true));
    expect(result.current.error).toBeNull();
  });

  it("logout 后状态变为未登录并清掉业务缓存", async () => {
    mockFetch({
      "GET /api/auth/status": jsonResponse(STATUS_IN),
      "POST /api/auth/logout": new Response(null, { status: 204 }),
    });
    const { client, wrapper } = setup();
    client.setQueryData(["shops"], [{ id: 1 }]);
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status?.logged_in).toBe(true));
    await act(() => result.current.logout());
    expect(result.current.status?.logged_in).toBe(false);
    expect(client.getQueryData(["shops"])).toBeUndefined();
  });

  it("changePassword 提交旧密码与新密码", async () => {
    const fetchMock = mockFetch({
      "GET /api/auth/status": jsonResponse(STATUS_IN),
      "POST /api/auth/password": new Response(null, { status: 204 }),
    });
    const { wrapper } = setup();
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.status).toBeDefined());
    await act(() => result.current.changePassword("old-password", "new-password"));
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/auth/password")!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ old_password: "old-password", new_password: "new-password" });
  });
});

describe("useUnauthorizedRedirect", () => {
  it("unauthorized_redirects: 业务请求 401 → 清空缓存并跳到 /login?next=当前路径", async () => {
    mockFetch({ "GET /api/shops": errorResponse(401, "Unauthorized", "请先登录") });
    const { client, wrapper } = setup("/shops?shops=1");
    client.setQueryData(["orders", [1], {}], { items: [] });
    const { result } = renderHook(
      () => {
        useUnauthorizedRedirect();
        return useLocation();
      },
      { wrapper },
    );
    await act(() => api.get("/api/shops").catch(() => undefined));
    await waitFor(() => expect(result.current.pathname).toBe("/login"));
    expect(result.current.search).toBe("?next=%2Fshops%3Fshops%3D1");
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });

  it("已经在 /login 时不重复跳转", async () => {
    mockFetch({ "GET /api/shops": errorResponse(401, "Unauthorized") });
    const { wrapper } = setup("/login?next=%2Forders");
    const { result } = renderHook(
      () => {
        useUnauthorizedRedirect();
        return useLocation();
      },
      { wrapper },
    );
    await act(() => api.get("/api/shops").catch(() => undefined));
    expect(result.current.search).toBe("?next=%2Forders");
  });
});

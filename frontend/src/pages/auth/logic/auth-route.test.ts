import { resolveAuthRoute } from "./auth-route";

const loggedOut = { setup_required: false, logged_in: false };
const loggedIn = { setup_required: false, logged_in: true };

describe("resolveAuthRoute", () => {
  it("route_setup_required: 任意路径都去 /setup", () => {
    const s = { setup_required: true, logged_in: false };
    expect(resolveAuthRoute(s, "/orders")).toBe("/setup");
    expect(resolveAuthRoute(s, "/login")).toBe("/setup");
    expect(resolveAuthRoute(s, "/shops?shops=1")).toBe("/setup");
  });

  it("需要初始化时已在 /setup 不再跳转", () => {
    expect(resolveAuthRoute({ setup_required: true, logged_in: false }, "/setup")).toBeNull();
  });

  it("route_login_with_next: 未登录带上原路径", () => {
    expect(resolveAuthRoute(loggedOut, "/shops?shops=1")).toBe("/login?next=%2Fshops%3Fshops%3D1");
  });

  it("未登录已在 /login 不再跳转", () => {
    expect(resolveAuthRoute(loggedOut, "/login")).toBeNull();
    expect(resolveAuthRoute(loggedOut, "/login?next=%2Fshops")).toBeNull();
  });

  it("未登录且无需初始化时访问 /setup 去 /login", () => {
    expect(resolveAuthRoute(loggedOut, "/setup")).toBe("/login");
  });

  it("route_logged_in_on_login: 已登录在 /login 回到 next", () => {
    expect(resolveAuthRoute(loggedIn, "/login?next=/shops")).toBe("/shops");
    expect(resolveAuthRoute(loggedIn, "/login?next=%2Fshops%3Fshops%3D1")).toBe("/shops?shops=1");
  });

  it("已登录在 /login 或 /setup 且无 next 去 /orders", () => {
    expect(resolveAuthRoute(loggedIn, "/login")).toBe("/orders");
    expect(resolveAuthRoute(loggedIn, "/setup")).toBe("/orders");
  });

  it.each(["//evil.example.com", "https://evil.example.com", "/login", "/setup?x=1", "orders"])(
    "不安全或循环的 next（%s）回落到 /orders",
    (next) => {
      expect(resolveAuthRoute(loggedIn, `/login?next=${encodeURIComponent(next)}`)).toBe("/orders");
    },
  );

  it("已登录访问其他页面不跳转", () => {
    expect(resolveAuthRoute(loggedIn, "/orders")).toBeNull();
    expect(resolveAuthRoute(loggedIn, "/shops?shops=1")).toBeNull();
  });
});

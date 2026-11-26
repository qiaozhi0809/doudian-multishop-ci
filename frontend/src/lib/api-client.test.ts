import { ApiError, FALLBACK_ERROR, api, errorText, setUnauthorizedHandler } from "./api-client";

function mockFetch(response: Response | Error) {
  const fn = vi.fn<typeof fetch>(async () => {
    if (response instanceof Error) throw response;
    return response.clone();
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** 期望 promise 被拒绝并返回 ApiError；若意外成功则测试失败。 */
const failure = (p: Promise<unknown>) =>
  p.then(
    () => {
      throw new Error("expected rejection");
    },
    (e: unknown) => e as ApiError,
  );

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

describe("api client", () => {
  it("api_error_from_envelope", async () => {
    mockFetch(json({ error: { type: "SessionExpired", message: "x", shop_id: 2 } }, 409));
    const err = await failure(api.get("/api/shops"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.type).toBe("SessionExpired");
    expect(err.shopId).toBe(2);
    expect(err.status).toBe(409);
    expect(err.message).toBe("x");
  });

  it("信封里的 detail 原样保留，缺 shop_id 为 null", async () => {
    mockFetch(json({ error: { type: "BizRejected", message: "m", detail: { code: 7 } } }, 422));
    const err = await failure(api.post("/api/orders/sync"));
    expect(err.shopId).toBeNull();
    expect(err.detail).toEqual({ code: 7 });
  });

  it("错误响应不是信封时回落为 HttpError", async () => {
    mockFetch(new Response("<html>bad gateway</html>", { status: 502 }));
    const err = await failure(api.get("/api/shops"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.type).toBe("HttpError");
    expect(err.status).toBe(502);
  });

  it("网络不通时抛 NetworkError", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const err = await failure(api.get("/api/shops"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.type).toBe("NetworkError");
    expect(err.status).toBe(0);
  });

  it("get 拼查询串：数组逗号连接，undefined 与 null 被忽略", async () => {
    const fetchMock = mockFetch(json({ items: [] }));
    await api.get("/api/orders", { shop_ids: [1, 2], status: undefined, page: 1, q: null });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/orders?shop_ids=1%2C2&page=1");
  });

  it("空数组不带该参数", async () => {
    const fetchMock = mockFetch(json({}));
    await api.get("/api/orders/counts", { shop_ids: [] });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/orders/counts");
  });

  it("post / patch / put 发送 JSON 请求体", async () => {
    const fetchMock = mockFetch(json({ ok: true }));
    await api.post("/api/auth/login", { username: "a", password: "b" });
    await api.patch("/api/shops/1", { name: "n" });
    await api.put("/api/shops/1/egress", { mode: "direct" });
    const calls = fetchMock.mock.calls as [string, RequestInit][];
    expect(calls.map(([, init]) => init.method)).toEqual(["POST", "PATCH", "PUT"]);
    expect(calls[0][1].body).toBe(JSON.stringify({ username: "a", password: "b" }));
    expect(new Headers(calls[0][1].headers).get("Content-Type")).toBe("application/json");
  });

  it("post 可带查询参数", async () => {
    const fetchMock = mockFetch(json({}));
    await api.post("/api/shops/1/egress/check", undefined, { accept_change: true });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/shops/1/egress/check?accept_change=true");
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBeUndefined();
  });

  it("204 空响应返回 undefined", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(api.post("/api/auth/logout")).resolves.toBeUndefined();
  });

  it("成功时返回解析后的 JSON", async () => {
    mockFetch(json({ setup_required: false, logged_in: true, username: "admin" }));
    await expect(api.get("/api/auth/status")).resolves.toEqual({
      setup_required: false,
      logged_in: true,
      username: "admin",
    });
  });

  describe("401 处理", () => {
    it("非 /api/auth/ 请求返回 401 时触发 onUnauthorized，并仍抛 ApiError", async () => {
      const handler = vi.fn();
      setUnauthorizedHandler(handler);
      mockFetch(json({ error: { type: "Unauthorized", message: "请先登录" } }, 401));
      const err = await failure(api.get("/api/shops"));
      expect(handler).toHaveBeenCalledTimes(1);
      expect(err.status).toBe(401);
    });

    it("/api/auth/* 的 401 不触发（登录失败由调用方自己处理）", async () => {
      const handler = vi.fn();
      setUnauthorizedHandler(handler);
      mockFetch(json({ error: { type: "Unauthorized", message: "x" } }, 401));
      await failure(api.post("/api/auth/login", { username: "a", password: "b" }));
      expect(handler).not.toHaveBeenCalled();
    });

    it("其他状态码不触发", async () => {
      const handler = vi.fn();
      setUnauthorizedHandler(handler);
      mockFetch(json({ error: { type: "SessionExpired", message: "x" } }, 409));
      await failure(api.get("/api/shops"));
      expect(handler).not.toHaveBeenCalled();
    });
  });
});

describe("errorText", () => {
  it("ApiError 用后端文案，其他异常用兜底文案", () => {
    expect(errorText(new ApiError({ type: "X", message: "端口必须是数字", status: 400 }))).toBe("端口必须是数字");
    expect(errorText(new Error("boom"))).toBe(FALLBACK_ERROR);
  });
});

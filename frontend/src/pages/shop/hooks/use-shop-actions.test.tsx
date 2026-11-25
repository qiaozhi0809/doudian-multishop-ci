import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useShopActions } from "./use-shop-actions";

const shops = [makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })];

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(() => useShopActions(shops), { wrapper });
  return { ...hook, invalidate };
}

let restore: () => void;
beforeEach(() => {
  restore = FakeEventSource.install();
});
afterEach(() => {
  restore();
  vi.useRealTimers();
});

const accepted = () => jsonResponse({ status: "started" }, 202);
const texts = (r: { current: ReturnType<typeof useShopActions> }) => r.current.notices.map((n) => n.text);

describe("扫码登录", () => {
  it("login_shows_waiting: 调用后进入等待态并提示去扫码；收到 active 事件后结束", async () => {
    mockFetch({ "POST /api/shops/1/login": accepted() });
    const { result } = setup();
    await act(() => result.current.login(1));
    expect(result.current.waitingShopIds).toContain(1);
    expect(texts(result)).toContain("店铺甲：请在弹出的浏览器窗口中扫码");

    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 1, status: "active" }));
    expect(result.current.waitingShopIds).not.toContain(1);
    expect(texts(result)).toEqual(["店铺甲：扫码登录成功"]);
  });

  it("login_failed_ends_waiting: 收到 shop_login_failed 结束等待并直接显示后端给出的原因", async () => {
    mockFetch({ "POST /api/shops/1/login": accepted() });
    const { result } = setup();
    await act(() => result.current.login(1));
    act(() => FakeEventSource.latest().emit("shop_login_failed", { shop_id: 1, reason: "扫码超时，请重新发起登录" }));
    expect(result.current.waitingShopIds).not.toContain(1);
    expect(result.current.notices).toEqual([
      expect.objectContaining({ tone: "danger", text: "店铺甲：扫码超时，请重新发起登录" }),
    ]);
  });

  it("其他店铺的事件，或不是 active 的状态变化，不结束等待", async () => {
    mockFetch({ "POST /api/shops/1/login": accepted() });
    const { result } = setup();
    await act(() => result.current.login(1));
    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 2, status: "active" }));
    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 1, status: "needs_login" }));
    act(() => FakeEventSource.latest().emit("shop_login_failed", { shop_id: 2, reason: "x" }));
    expect(result.current.waitingShopIds).toEqual([1]);
  });

  it("接口预检失败（409）时不进入等待态，直接显示后端的中文原因", async () => {
    mockFetch({ "POST /api/shops/1/login": errorResponse(409, "EgressNotReady", "出口未检查通过，不能扫码", 1) });
    const { result } = setup();
    await act(() => result.current.login(1));
    expect(result.current.waitingShopIds).toEqual([]);
    expect(result.current.notices).toEqual([
      expect.objectContaining({ tone: "danger", text: "店铺甲：出口未检查通过，不能扫码" }),
    ]);
  });

  it("等待超时后结束并提示重新发起", async () => {
    vi.useFakeTimers();
    mockFetch({ "POST /api/shops/1/login": accepted() });
    const { result } = setup();
    await act(() => result.current.login(1));
    act(() => vi.advanceTimersByTime(10 * 60 * 1000 + 1));
    expect(result.current.waitingShopIds).toEqual([]);
    expect(texts(result)).toEqual(["店铺甲：等待扫码超时，请重新发起扫码登录"]);
  });
});

describe("其他操作", () => {
  it("probe 成功后刷新店铺并就地提示，失败显示原因", async () => {
    mockFetch({ "POST /api/shops/1/probe": jsonResponse(shops[0]), "POST /api/shops/2/probe": errorResponse(409, "SessionExpired", "会话已过期，请重新扫码登录", 2) });
    const { result, invalidate } = setup();
    await act(() => result.current.probe(1));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["shops"] });
    expect(texts(result)).toContain("店铺甲：探测完成");
    await act(() => result.current.probe(2));
    expect(texts(result)).toContain("店铺乙：会话已过期，请重新扫码登录");
  });

  it("syncBase 提示各项数量与就绪情况", async () => {
    mockFetch({
      "POST /api/shops/1/sync-base": jsonResponse({ addresses: 2, couriers: 5, templates: 3, accounts: 1, ready_for_label: false, not_ready_reasons: ["缺少默认发货地址"] }),
    });
    const { result } = setup();
    await act(() => result.current.syncBase(1));
    expect(texts(result)).toContain("店铺甲：基础数据已同步（地址 2、快递 5、模板 3、面单账户 1），未就绪：缺少默认发货地址");
  });

  it("checkEgress 确认新 IP 时带 accept_change=true", async () => {
    const fetchMock = mockFetch({
      "POST /api/shops/1/egress/check": jsonResponse({ egress_ip: "1.2.3.5", egress_ip_pending: null, egress_status: "ok" }),
    });
    const { result } = setup();
    await act(() => result.current.checkEgress(1, true));
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/shops/1/egress/check?accept_change=true");
    expect(texts(result)).toContain("店铺甲：出口正常 · 1.2.3.5");
  });

  it("checkEgress 结果不是 ok 时按状态提示", async () => {
    mockFetch({
      "POST /api/shops/1/egress/check": jsonResponse({ egress_ip: null, egress_ip_pending: null, egress_status: "unreachable" }),
    });
    const { result } = setup();
    await act(() => result.current.checkEgress(1));
    expect(result.current.notices[0]).toMatchObject({ tone: "danger", text: "店铺甲：出口不通，请检查代理是否到期或更换代理" });
  });

  it("resume 成功后提示已恢复", async () => {
    mockFetch({ "POST /api/shops/1/resume": jsonResponse(shops[0]) });
    const { result } = setup();
    await act(() => result.current.resume(1));
    expect(texts(result)).toContain("店铺甲：已解除风控暂停");
  });

  it("setEgress 成功返回 true；失败返回 false 并给出原因（不进通知）", async () => {
    mockFetch({
      "PUT /api/shops/1/egress": jsonResponse(shops[0]),
      "PUT /api/shops/2/egress": errorResponse(422, "InvalidRequest", "端口必须是数字"),
    });
    const { result } = setup();
    let ok: { ok: boolean; error: string | null } | undefined;
    await act(async () => {
      ok = await result.current.setEgress(1, { mode: "direct" });
    });
    expect(ok).toEqual({ ok: true, error: null });
    await act(async () => {
      ok = await result.current.setEgress(2, { mode: "direct" });
    });
    expect(ok).toEqual({ ok: false, error: "端口必须是数字" });
  });

  it("addShop 成功返回新店铺并提示去设置出口", async () => {
    mockFetch({ "POST /api/shops": jsonResponse(makeShop({ id: 9, name: "新店" }), 201) });
    const { result } = setup();
    let created: unknown;
    await act(async () => {
      created = await result.current.addShop({ name: "新店" });
    });
    expect(created).toMatchObject({ ok: true, shop: { id: 9 } });
    expect(texts(result)).toContain("已添加「新店」，请先设置出口并检查通过，再扫码登录");
  });

  it("操作进行中 pending 含对应键，结束后移除", async () => {
    let release!: () => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(jsonResponse(shops[0]));
          }),
      ),
    );
    const { result } = setup();
    let p!: Promise<unknown>;
    act(() => {
      p = result.current.probe(1);
    });
    expect(result.current.pending).toContain("probe:1");
    await act(async () => {
      release();
      await p;
    });
    await waitFor(() => expect(result.current.pending).toEqual([]));
  });

  it("通知可以逐条关闭", async () => {
    mockFetch({ "POST /api/shops/1/resume": jsonResponse(shops[0]) });
    const { result } = setup();
    await act(() => result.current.resume(1));
    act(() => result.current.dismissNotice(result.current.notices[0].id));
    expect(result.current.notices).toEqual([]);
  });
});

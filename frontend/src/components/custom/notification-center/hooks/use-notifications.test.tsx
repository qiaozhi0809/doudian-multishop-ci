import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import type { NotificationItem } from "../logic/notification-view";
import { ALERTED_KEY, useNotificationAlerts, useNotifications } from "./use-notifications";

const item = (over: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 1, kind: "login_expired", level: "strong", shop_id: 1, state_key: "login:1", title: "示例店 登录失效",
  body: null, link: "/shops?shop=1", count: 1, read_at: null, resolved_at: null,
  created_at: "2026-11-25T08:00:00", updated_at: "2026-11-25T08:00:00", ...over,
});

const summary = { unread: 2, strong_open: [{ shop_id: 1, shop_name: "示例店", kinds: ["login_expired"], link: "/shops?shop=1" }] };

function routes() {
  return mockFetch({
    "GET /api/notifications": jsonResponse({ items: [item()], total: 1, page: 1, page_size: 20 }),
    "GET /api/notifications/summary": jsonResponse(summary),
    "POST /api/notifications/1/read": new Response(null, { status: 204 }),
    "POST /api/notifications/read-all": new Response(null, { status: 204 }),
  });
}

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const Wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { Wrapper, invalidate };
}

const calls = (fetch: ReturnType<typeof mockFetch>, path: string) =>
  fetch.mock.calls.filter(([url]) => String(url).split("?")[0] === path).length;

let restore: () => void;
beforeEach(() => {
  sessionStorage.clear();
  restore = FakeEventSource.install();
});
afterEach(() => restore());

describe("useNotifications", () => {
  it("读取列表与摘要", async () => {
    routes();
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.items).toHaveLength(1));
    await waitFor(() => expect(result.current.unread).toBe(2));
    expect(result.current.strongOpen).toEqual(summary.strong_open);
    expect(result.current.loading).toBe(false);
  });

  it("只看未读时带 unread 参数并回到第 1 页", async () => {
    const fetch = routes();
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    act(() => result.current.setPage(3));
    act(() => result.current.setUnreadOnly(true));
    expect(result.current.page).toBe(1);
    await waitFor(() =>
      expect(fetch.mock.calls.some(([url]) => String(url) === "/api/notifications?unread=true&page=1")).toBe(true),
    );
  });

  it("只看未读时最后一页清空，退回最后一个有内容的页", async () => {
    const fetch = mockFetch({
      "GET /api/notifications": () => {
        const url = String(fetch.mock.calls.at(-1)?.[0] ?? "");
        const page = Number(new URLSearchParams(url.split("?")[1]).get("page") ?? 1);
        return jsonResponse({ items: page >= 4 ? [] : [item({ id: page })], total: 41, page, page_size: 20 });
      },
      "GET /api/notifications/summary": jsonResponse(summary),
    });
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    act(() => result.current.setPage(4));
    await waitFor(() => expect(result.current.page).toBe(3));
  });

  it("第 1 页以外为空且总数为 0 时回到第 1 页", async () => {
    mockFetch({
      "GET /api/notifications": jsonResponse({ items: [], total: 0, page: 2, page_size: 20 }),
      "GET /api/notifications/summary": jsonResponse(summary),
    });
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    act(() => result.current.setPage(2));
    await waitFor(() => expect(result.current.page).toBe(1));
  });

  it("收到 notification 事件后重新拉取摘要与列表", async () => {
    const fetch = routes();
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.unread).toBe(2));
    const before = calls(fetch, "/api/notifications/summary");
    const listBefore = calls(fetch, "/api/notifications");
    act(() => FakeEventSource.latest().emit("notification", { action: "created", item: item({ id: 2 }), alert: true }));
    await waitFor(() => expect(calls(fetch, "/api/notifications/summary")).toBe(before + 1));
    await waitFor(() => expect(calls(fetch, "/api/notifications")).toBe(listBefore + 1));
  });

  it("SSE 重连后重新拉取摘要与列表", async () => {
    const fetch = routes();
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.unread).toBe(2));
    const before = calls(fetch, "/api/notifications/summary");
    const listBefore = calls(fetch, "/api/notifications");
    act(() => FakeEventSource.latest().emit("open"));
    await waitFor(() => expect(calls(fetch, "/api/notifications/summary")).toBe(before + 1));
    await waitFor(() => expect(calls(fetch, "/api/notifications")).toBe(listBefore + 1));
  });

  it("单条已读与全部已读调用接口并失效通知查询", async () => {
    const fetch = routes();
    const { Wrapper, invalidate } = wrapper();
    const { result } = renderHook(() => useNotifications(), { wrapper: Wrapper });
    await act(async () => {
      expect(await result.current.markRead(1)).toEqual({ ok: true });
      expect(await result.current.markAllRead()).toEqual({ ok: true });
    });
    expect(calls(fetch, "/api/notifications/1/read")).toBe(1);
    expect(calls(fetch, "/api/notifications/read-all")).toBe(1);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["notifications"] });
  });
});

describe("useNotificationAlerts", () => {
  it("同一 alert（id + 数量）只回调一次，记在 sessionStorage", () => {
    const onAlert = vi.fn();
    renderHook(() => useNotificationAlerts(onAlert));
    const event = { action: "created", item: item({ id: 7 }), alert: true };
    act(() => FakeEventSource.latest().emit("notification", event));
    act(() => FakeEventSource.latest().emit("notification", event));
    expect(onAlert).toHaveBeenCalledTimes(1);
    expect(onAlert).toHaveBeenCalledWith(event.item);
    expect(JSON.parse(sessionStorage.getItem(ALERTED_KEY) ?? "[]")).toEqual(["7:1"]);
  });

  it("未读时又来新售后：同一条合并后数量变多，再回调一次", () => {
    const onAlert = vi.fn();
    renderHook(() => useNotificationAlerts(onAlert));
    act(() => FakeEventSource.latest().emit("notification", { action: "created", item: item({ id: 7 }), alert: true }));
    act(() => FakeEventSource.latest().emit("notification", { action: "updated", item: item({ id: 7, count: 2 }), alert: true }));
    expect(onAlert).toHaveBeenCalledTimes(2);
  });

  it("刷新后（sessionStorage 已有该 id + 数量）不再回调", () => {
    sessionStorage.setItem(ALERTED_KEY, JSON.stringify(["7:1"]));
    const onAlert = vi.fn();
    renderHook(() => useNotificationAlerts(onAlert));
    act(() => FakeEventSource.latest().emit("notification", { action: "created", item: item({ id: 7 }), alert: true }));
    expect(onAlert).not.toHaveBeenCalled();
  });

  it("alert=false 的事件不回调", () => {
    const onAlert = vi.fn();
    renderHook(() => useNotificationAlerts(onAlert));
    act(() => FakeEventSource.latest().emit("notification", { action: "updated", item: item({ id: 8 }), alert: false }));
    expect(onAlert).not.toHaveBeenCalled();
  });
});

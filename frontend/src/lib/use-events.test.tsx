import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { queryKeys } from "./query-keys";
import { useEventSubscription, useEvents } from "./use-events";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  private listeners = new Map<string, Set<(e: unknown) => void>>();
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: (e: unknown) => void) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name)!.add(fn);
  }
  removeEventListener(name: string, fn: (e: unknown) => void) {
    this.listeners.get(name)?.delete(fn);
  }
  close() {
    this.closed = true;
  }
  emit(name: string, data?: unknown) {
    const event = data === undefined ? new Event(name) : Object.assign(new Event(name), { data: JSON.stringify(data) });
    this.listeners.get(name)?.forEach((fn) => fn(event));
  }
}

const latest = () => FakeEventSource.instances[FakeEventSource.instances.length - 1];

function setup() {
  const client = new QueryClient();
  const spy = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { spy, wrapper };
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});
afterEach(() => vi.unstubAllGlobals());

describe("useEventSubscription", () => {
  it("event_subscription_receives_data", () => {
    const handler = vi.fn();
    const { wrapper } = setup();
    renderHook(() => useEventSubscription("shop_login_failed", handler), { wrapper });
    act(() => latest().emit("shop_login_failed", { shop_id: 1, reason: "timeout" }));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith({ shop_id: 1, reason: "timeout" });
  });

  it("卸载后退订，不再收到事件", () => {
    const handler = vi.fn();
    const { wrapper } = setup();
    const { unmount } = renderHook(() => useEventSubscription("shop_login_failed", handler), { wrapper });
    const source = latest();
    unmount();
    act(() => source.emit("shop_login_failed", { shop_id: 1, reason: "x" }));
    expect(handler).not.toHaveBeenCalled();
  });

  it("handler 变化时用最新的，且不重建连接", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { wrapper } = setup();
    const { rerender } = renderHook(({ h }) => useEventSubscription("sync_progress", h), {
      wrapper,
      initialProps: { h: first },
    });
    rerender({ h: second });
    act(() => latest().emit("sync_progress", { shop_id: 1 }));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("无法解析的事件数据被忽略，不抛错", () => {
    const handler = vi.fn();
    const { wrapper } = setup();
    renderHook(() => useEventSubscription("sync_progress", handler), { wrapper });
    const bad = Object.assign(new Event("sync_progress"), { data: "{not json" });
    expect(() => act(() => (latest() as unknown as { listeners: Map<string, Set<(e: unknown) => void>> })
      .listeners.get("sync_progress")!.forEach((fn) => fn(bad)))).not.toThrow();
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("useEvents", () => {
  it("use_events_invalidates: shop_status_changed 失效店铺", () => {
    const { spy, wrapper } = setup();
    renderHook(() => useEvents(), { wrapper });
    spy.mockClear();
    act(() => latest().emit("shop_status_changed", { shop_id: 1, status: "active" }));
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.shops() });
  });

  describe("sync_progress 尾部节流", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("1 秒后失效订单与订单计数", () => {
      const { spy, wrapper } = setup();
      renderHook(() => useEvents(), { wrapper });
      spy.mockClear();
      act(() => latest().emit("sync_progress", { shop_id: 1, kind: "orders", fetched: 10 }));
      expect(spy).not.toHaveBeenCalled();
      act(() => vi.advanceTimersByTime(1000));
      expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.ordersRoot() });
      expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.orderCountsRoot() });
    });

    it("sync_progress_throttled: 1 秒内连续 5 次只触发 1 次失效", () => {
      const { spy, wrapper } = setup();
      renderHook(() => useEvents(), { wrapper });
      spy.mockClear();
      for (let i = 0; i < 5; i++) {
        act(() => latest().emit("sync_progress", { shop_id: 1, kind: "orders", fetched: i * 200 }));
        act(() => vi.advanceTimersByTime(100));
      }
      act(() => vi.advanceTimersByTime(1000));
      const roots = spy.mock.calls.filter(([f]) => f?.queryKey?.[0] === "orders");
      expect(roots).toHaveLength(1);
      expect(spy).toHaveBeenCalledTimes(2); // orders + orderCounts 各一次
    });

    it("窗口过后的下一次 sync_progress 再次触发", () => {
      const { spy, wrapper } = setup();
      renderHook(() => useEvents(), { wrapper });
      spy.mockClear();
      act(() => latest().emit("sync_progress", {}));
      act(() => vi.advanceTimersByTime(1000));
      act(() => latest().emit("sync_progress", {}));
      act(() => vi.advanceTimersByTime(1000));
      expect(spy).toHaveBeenCalledTimes(4);
    });

    it("卸载后取消待执行的失效", () => {
      const { spy, wrapper } = setup();
      const { unmount } = renderHook(() => useEvents(), { wrapper });
      spy.mockClear();
      act(() => latest().emit("sync_progress", {}));
      unmount();
      act(() => vi.advanceTimersByTime(2000));
      expect(spy).not.toHaveBeenCalled();
    });

    it("shop_status_changed 与 open 不被节流，立即失效", () => {
      const { spy, wrapper } = setup();
      renderHook(() => useEvents(), { wrapper });
      spy.mockClear();
      act(() => latest().emit("shop_status_changed", { shop_id: 1, status: "active" }));
      act(() => latest().emit("open"));
      expect(spy).toHaveBeenCalledTimes(2);
    });
  });

  it("连接 open（含重连）时失效全部", () => {
    const { spy, wrapper } = setup();
    renderHook(() => useEvents(), { wrapper });
    spy.mockClear();
    act(() => latest().emit("open"));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenLastCalledWith();
    act(() => latest().emit("open"));
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("useEvents 与 useEventSubscription 共用同一个 EventSource", () => {
    const { wrapper } = setup();
    renderHook(
      () => {
        useEvents();
        useEventSubscription("shop_login_failed", () => {});
      },
      { wrapper },
    );
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().url).toBe("/api/events");
  });

  it("最后一个订阅者卸载后关闭连接", () => {
    const { wrapper } = setup();
    const { unmount } = renderHook(() => useEvents(), { wrapper });
    const source = latest();
    unmount();
    expect(source.closed).toBe(true);
  });
});

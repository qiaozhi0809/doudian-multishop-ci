import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { queryKeys } from "@/lib/query-keys";
import { FakeEventSource } from "@/test/fake-event-source";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useQuickLogin } from "./use-quick-login";

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const hook = renderHook(() => useQuickLogin(), { wrapper });
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

describe("顶栏一键重登", () => {
  it("发起登录后进入等待态；收到 active 结束等待并刷新店铺", async () => {
    mockFetch({ "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) });
    const { result, invalidate } = setup();
    await act(async () => {
      await result.current.login(2);
    });
    expect(result.current.waitingIds).toEqual([2]);
    expect(result.current.pendingIds).toEqual([]);

    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 2, status: "active" }));
    expect(result.current.waitingIds).toEqual([]);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.shops() });
  });

  it("shop_login_failed 结束等待，并把后端原因留在这一行", async () => {
    mockFetch({ "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) });
    const { result } = setup();
    await act(async () => {
      await result.current.login(2);
    });
    act(() =>
      FakeEventSource.latest().emit("shop_login_failed", { shop_id: 2, reason: "扫码超时，请重新发起登录" }),
    );
    expect(result.current.waitingIds).toEqual([]);
    expect(result.current.errors[2]).toBe("扫码超时，请重新发起登录");
  });

  it("接口预检失败时不进入等待态，直接显示中文原因", async () => {
    mockFetch({
      "POST /api/shops/2/login": errorResponse(409, "EgressNotReady", "出口未检查通过，不能扫码", 2),
    });
    const { result } = setup();
    await act(async () => {
      await result.current.login(2);
    });
    expect(result.current.waitingIds).toEqual([]);
    expect(result.current.errors[2]).toBe("出口未检查通过，不能扫码");
  });

  it("等待超时后结束并提示重新发起", async () => {
    vi.useFakeTimers();
    mockFetch({ "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) });
    const { result } = setup();
    await act(async () => {
      await result.current.login(2);
    });
    expect(result.current.waitingIds).toEqual([2]);
    act(() => vi.advanceTimersByTime(10 * 60 * 1000));
    expect(result.current.waitingIds).toEqual([]);
    expect(result.current.errors[2]).toBe("等待扫码超时，请重新发起扫码登录");
  });

  it("其他店铺的事件不影响本店的等待态", async () => {
    mockFetch({ "POST /api/shops/2/login": jsonResponse({ status: "started" }, 202) });
    const { result } = setup();
    await act(async () => {
      await result.current.login(2);
    });
    act(() => FakeEventSource.latest().emit("shop_status_changed", { shop_id: 3, status: "active" }));
    act(() => FakeEventSource.latest().emit("shop_login_failed", { shop_id: 3, reason: "x" }));
    expect(result.current.waitingIds).toEqual([2]);
    expect(result.current.errors[3]).toBeUndefined();
  });
});

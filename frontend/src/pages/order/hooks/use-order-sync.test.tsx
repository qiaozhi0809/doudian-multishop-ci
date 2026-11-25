import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useOrderSync } from "./use-order-sync";

function setup(path = "/orders") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return { ...renderHook(() => useOrderSync(), { wrapper }), invalidate };
}

afterEach(() => vi.unstubAllGlobals());

describe("useOrderSync", () => {
  it("同步当前筛选的店铺，并区分已开始与正在同步", async () => {
    const fetchMock = mockFetch({ "POST /api/orders/sync": jsonResponse({ started: [1], already_running: [2] }, 202) });
    const { result, invalidate } = setup("/orders?shops=1,2");
    await act(() => result.current.sync());
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/orders/sync?shop_ids=1%2C2");
    expect(result.current.message).toEqual({ tone: "success", text: "已开始同步 1 家店，1 家店正在同步中" });
    expect(invalidate).toHaveBeenCalled();
  });

  it("没有店铺筛选时不带 shop_ids（全部店铺）", async () => {
    const fetchMock = mockFetch({ "POST /api/orders/sync": jsonResponse({ started: [1], already_running: [] }, 202) });
    const { result } = setup();
    await act(() => result.current.sync());
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/orders/sync");
  });

  it("失败时显示后端给出的原因（409 暂停等），可关闭", async () => {
    mockFetch({ "POST /api/orders/sync": errorResponse(409, "ShopPaused", "店铺已被风控暂停，请先恢复", 1) });
    const { result } = setup();
    await act(() => result.current.sync());
    expect(result.current.message).toEqual({ tone: "danger", text: "店铺已被风控暂停，请先恢复" });
    act(() => result.current.dismiss());
    expect(result.current.message).toBeNull();
  });

  it("进行中 pending 为 true", async () => {
    let release!: () => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((r) => { release = () => r(jsonResponse({ started: [], already_running: [] }, 202)); })));
    const { result } = setup();
    let p!: Promise<void>;
    act(() => { p = result.current.sync(); });
    expect(result.current.pending).toBe(true);
    await act(async () => { release(); await p; });
    expect(result.current.pending).toBe(false);
  });
});

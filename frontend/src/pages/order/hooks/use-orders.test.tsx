import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useOrders } from "./use-orders";

const PAGE = { items: [], total: 120, page: 1, page_size: 50 };

function setup(path: string) {
  const fetchMock = mockFetch({ "GET /api/orders": jsonResponse(PAGE) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  const hook = renderHook(() => ({ orders: useOrders(), filter: useShopFilter(), location: useLocation() }), { wrapper });
  return { ...hook, fetchMock };
}

afterEach(() => vi.unstubAllGlobals());

const lastUrl = (m: ReturnType<typeof setup>["fetchMock"]) => String(m.mock.calls[m.mock.calls.length - 1][0]);

describe("useOrders", () => {
  it("请求带店铺筛选、本地状态、页码，每页 50，页码从 1 开始", async () => {
    const { result, fetchMock } = setup("/orders?shops=1,2&status=shipped&page=3");
    await waitFor(() => expect(result.current.orders.query.data).toBeDefined());
    expect(lastUrl(fetchMock)).toBe("/api/orders?shop_ids=1%2C2&status=shipped&page=3&page_size=50");
  });

  it("没有参数时：第 1 页、全部状态、全部店铺", async () => {
    const { result, fetchMock } = setup("/orders");
    await waitFor(() => expect(result.current.orders.query.data).toBeDefined());
    expect(result.current.orders).toMatchObject({ page: 1, status: undefined, shopIds: [] });
    expect(lastUrl(fetchMock)).toBe("/api/orders?page=1&page_size=50");
  });

  it("URL 里不合法的页码与状态被忽略", async () => {
    const { result } = setup("/orders?page=0&status=nope");
    expect(result.current.orders).toMatchObject({ page: 1, status: undefined });
    const second = setup("/orders?page=abc");
    expect(second.result.current.orders.page).toBe(1);
  });

  it("翻页写入 URL；回到第 1 页时去掉 page 参数", async () => {
    const { result } = setup("/orders?status=shipped");
    act(() => result.current.orders.setPage(3));
    expect(result.current.location.search).toBe("?status=shipped&page=3");
    act(() => result.current.orders.setPage(1));
    expect(result.current.location.search).toBe("?status=shipped");
  });

  it("切换本地状态回到第 1 页；选择全部时去掉 status", async () => {
    const { result } = setup("/orders?page=4");
    act(() => result.current.orders.setStatus("exception"));
    expect(result.current.location.search).toBe("?status=exception");
    act(() => result.current.orders.setStatus(undefined));
    expect(result.current.location.search).toBe("");
  });

  it("reset_page_on_filter_change: 切换店铺筛选后 page 回到 1", async () => {
    const { result } = setup("/orders?shops=1&page=4");
    expect(result.current.orders.page).toBe(4);
    act(() => result.current.filter.setShopIds([2]));
    expect(result.current.orders.page).toBe(1);
    expect(result.current.location.search).toBe("?shops=2");
  });
});

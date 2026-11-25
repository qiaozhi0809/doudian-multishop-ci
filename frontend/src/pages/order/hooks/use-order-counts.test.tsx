import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useOrderCounts } from "./use-order-counts";

function setup(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return renderHook(() => useOrderCounts(), { wrapper });
}

afterEach(() => vi.unstubAllGlobals());

describe("useOrderCounts", () => {
  it("按店铺筛选请求，并汇总成合计与失败店", async () => {
    const fetchMock = mockFetch({
      "GET /api/orders/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", counts: { stock_up: 5, exp_ship: 1, ship_delay: 0, in_aftersale: 2 }, fetched_at: "2026-11-25T01:00:00Z" },
          { shop_id: 2, source: "error", error: "出口不通" },
        ],
      }),
    });
    const { result } = setup("/orders?shops=1,2");
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/orders/counts?shop_ids=1%2C2");
    expect(result.current.data?.totals.stock_up).toBe(5);
    expect(result.current.data?.failedShopIds).toEqual([2]);
  });
});

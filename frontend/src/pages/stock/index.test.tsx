import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import StockPage from "./index";
import { WarehouseList } from "./components/stock-summary";

const stock = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", product_id: "3811109459833520578",
  name: "测试商品 A", total_stock_num: 12, spot_stock_num: 10, future_stock_num: 2,
  total_occupied_stock_num: 3, total_unoccupied_stock_num: 9,
  is_alarming: false, synced_at: "2026-11-25T00:00:00Z", ...over,
});

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/stock"]}>
        <Routes>
          <Route path="/stock" element={<StockPage />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("库存聚合页", () => {
  it("显示库存行、预警汇总与仓库", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/stock": jsonResponse({
        items: [stock(), stock({ id: 2, product_id: "p2", name: "商品 B", is_alarming: true })],
        total: 2, page: 1, page_size: 50,
      }),
      "GET /api/catalog/stock/summary": jsonResponse({
        total: 2, alarm_count: 1, sold_out_count: 1,
      }),
      "GET /api/catalog/stock/warehouses": jsonResponse({
        shops: [{ shop_id: 1, source: "upstream", error: null, fetched_at: null,
                  items: [{ warehouse_id: "w1", name: "主仓" }] }],
      }),
    });
    renderPage();
    const tableRow = within(await screen.findByRole("row", { name: /3811109459833520578/ }));
    expect(tableRow.getByText("测试商品 A")).toBeInTheDocument();
    expect(tableRow.getByText("12")).toBeInTheDocument();
    expect(tableRow.getByText("10")).toBeInTheDocument();
    expect(tableRow.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("库存预警")).toBeInTheDocument();
    expect(screen.getByText("主仓")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /商品 B/ })).toHaveTextContent("预警");
  });

  it("点计数卡筛列表：预警卡带 quick=alarm 发给后端，再点清除；「商品数」卡也清除", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1 })]),
      "GET /api/catalog/stock": jsonResponse({ items: [stock()], total: 1, page: 1, page_size: 50 }),
      "GET /api/catalog/stock/summary": jsonResponse({ total: 1, alarm_count: 0, sold_out_count: 0 }),
      "GET /api/catalog/stock/warehouses": jsonResponse({ shops: [] }),
    });
    renderPage();
    await screen.findByRole("row", { name: /3811109459833520578/ });
    const user = userEvent.setup();
    const alarm = screen.getByRole("button", { name: /库存预警/ });
    expect(alarm).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /商品数/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(alarm);
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("quick=alarm"));
    expect(screen.getByRole("button", { name: /库存预警/ })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/catalog/stock?") && String(url).includes("quick=alarm"))).toBe(true),
    );
    await user.click(screen.getByRole("button", { name: /库存预警/ }));
    await waitFor(() => expect(screen.getByTestId("where")).not.toHaveTextContent("quick="));
    await user.click(screen.getByRole("button", { name: /售罄/ }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("quick=sold_out"));
    await user.click(screen.getByRole("button", { name: /商品数/ }));
    await waitFor(() => expect(screen.getByTestId("where")).not.toHaveTextContent("quick="));
  });

  it("空列表只显示「没有符合条件的库存记录」", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/stock": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/catalog/stock/summary": jsonResponse({ total: 0, alarm_count: 0, sold_out_count: 0 }),
      "GET /api/catalog/stock/warehouses": jsonResponse({ shops: [] }),
    });
    renderPage();
    expect(await screen.findByRole("cell", { name: "没有符合条件的库存记录" })).toBeInTheDocument();
  });

  it("仓库是附属信息：读取中不占位，不在卡片和表格之间留骨架条", () => {
    render(<WarehouseList shops={[]} shopName={() => "店铺甲"} loading />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

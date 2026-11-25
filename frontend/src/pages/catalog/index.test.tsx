import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import CatalogPage from "./index";

const product = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", product_id: "3811109459833520578",
  name: "测试商品 A", status: "1", tab: "onSale", price_lower_cents: 12800,
  price_higher_cents: 12800, stock_num: 12, sell_num: 3,
  synced_at: "2026-11-25T00:00:00Z",
  display: { img: null, product_url: null, category_name: "测试类目", quality_score: 4.8, sell_num_30d: 2 },
  ...over,
});

const counts = jsonResponse({
  shops: [{
    shop_id: 1, source: "upstream", error: null, fetched_at: new Date().toISOString(),
    counts: { onsale: 6, audit: 0, unpass: 0, draft: 0, forbidden: 0, sell_out_new: 1 },
  }],
});

const groups = jsonResponse({
  shops: [{ shop_id: 1, source: "upstream", error: null, fetched_at: null,
            items: [{ group_id: "1001", name: "默认分组" }] }],
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/catalog"]}>
        <Routes>
          <Route path="/catalog" element={<CatalogPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("商品聚合页", () => {
  it("显示商品行、状态计数与分组", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/products": jsonResponse({
        items: [product()], total: 1, page: 1, page_size: 50,
      }),
      "GET /api/catalog/products/counts": counts,
      "GET /api/catalog/products/groups": groups,
    });
    renderPage();
    const tableRow = within(await screen.findByRole("row", { name: /3811109459833520578/ }));
    expect(tableRow.getByText("测试商品 A")).toBeInTheDocument();
    expect(tableRow.getByText("¥128.00")).toBeInTheDocument();
    expect(tableRow.getByText("onSale")).toBeInTheDocument();
    expect(tableRow.getByText("测试类目")).toBeInTheDocument();
    expect(await screen.findByText("在售")).toBeInTheDocument();
    expect(await screen.findByText("默认分组")).toBeInTheDocument();
    expect(screen.getByLabelText("搜索商品")).toBeInTheDocument();
  });
});

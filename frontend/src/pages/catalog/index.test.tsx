import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { makeShop, strongOpenSummary } from "@/test/fixtures";
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
    expect(tableRow.getByText("在售")).toBeInTheDocument();
    expect(tableRow.getByText("测试类目")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /在售/ })).toHaveAttribute("aria-pressed", "false");
    expect(await screen.findByText("默认分组")).toBeInTheDocument();
    expect(screen.getByLabelText("搜索商品")).toBeInTheDocument();
  });

  it("未取到计数的店已在顶部横条时不再提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })]),
      "GET /api/catalog/products": jsonResponse({ items: [product()], total: 1, page: 1, page_size: 50 }),
      "GET /api/catalog/products/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", error: null, fetched_at: null, counts: { onsale: 6 } },
          { shop_id: 2, source: "error", error: "风控暂停", fetched_at: null, counts: {} },
        ],
      }),
      "GET /api/catalog/products/groups": groups,
      "GET /api/notifications/summary": jsonResponse(strongOpenSummary([{ shopId: 2, kinds: ["risk_paused"] }])),
    });
    renderPage();
    expect(await screen.findByRole("button", { name: /在售/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/家店未取到/)).not.toBeInTheDocument());
  });

  it("部分店铺计数失败：提示 N 家店未取到，可展开原因", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })]),
      "GET /api/catalog/products": jsonResponse({ items: [product()], total: 1, page: 1, page_size: 50 }),
      "GET /api/catalog/products/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", error: null, fetched_at: null, counts: { onsale: 6 } },
          { shop_id: 2, source: "error", error: "平台接口报错", fetched_at: null, counts: {} },
        ],
      }),
      "GET /api/catalog/products/groups": groups,
    });
    renderPage();
    expect(await screen.findByText("1 家店未取到")).toBeInTheDocument();
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByRole("listitem")).toHaveTextContent("店铺乙：平台接口报错");
  });

  it("点计数卡筛列表：快捷筛选与关键字、排序一起发给后端，换筛选回到第 1 页，再点清除", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/products": jsonResponse({ items: [product()], total: 1, page: 1, page_size: 50 }),
      "GET /api/catalog/products/counts": counts,
      "GET /api/catalog/products/groups": groups,
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/catalog?q=测试&sort=price&order=desc&page=2"]}>
          <Routes>
            <Route path="/catalog" element={<CatalogPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();
    const draft = await screen.findByRole("button", { name: /草稿/ });
    await user.click(draft);
    const listUrls = () =>
      fetchMock.mock.calls.map(([u]) => decodeURIComponent(String(u))).filter((u) => u.startsWith("/api/catalog/products?"));
    await waitFor(() =>
      expect(listUrls()).toContain("/api/catalog/products?keyword=测试&page=1&page_size=50&sort=price&order=desc&quick=draft"),
    );
    expect(screen.getByRole("button", { name: /草稿/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /草稿/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /草稿/ })).toHaveAttribute("aria-pressed", "false"));
    expect(listUrls().at(-1)).toBe("/api/catalog/products?keyword=测试&page=1&page_size=50&sort=price&order=desc");
  });

  it("空列表只显示「没有符合条件的商品」，没有分组时不放说明小字", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/products": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/catalog/products/counts": counts,
      "GET /api/catalog/products/groups": jsonResponse({
        shops: [{ shop_id: 1, source: "upstream", error: null, fetched_at: null, items: [] }],
      }),
    });
    renderPage();
    expect(await screen.findByRole("cell", { name: "没有符合条件的商品" })).toBeInTheDocument();
    expect(await screen.findByText("在售")).toBeInTheDocument();
    expect(screen.queryByText(/还没有商品分组/)).not.toBeInTheDocument();
    expect(screen.queryByText(/同步商品」/)).not.toBeInTheDocument();
  });

  it("分组读取失败只提示失败本身", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/catalog/products": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/catalog/products/counts": counts,
      "GET /api/catalog/products/groups": jsonResponse({ detail: "boom" }, 500),
    });
    renderPage();
    expect(await screen.findByText("商品分组读取失败")).toBeInTheDocument();
  });
});

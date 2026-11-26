import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import FundPage from "./index";

const unsettled = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", shop_order_no: "6900000000000000001",
  sku_order_no: "6900000000000000001-1", product_id: "3811109459833520578",
  income_amount_cents: 25800, unsettled_amount_cents: 25284,
  platform_service_fee_cents: -516, ecom_order_status: "已发货",
  expected_settle_time: "订单确认收货或核销21天后结算",
  settle_period_detail: '{"delay_day": 21}', synced_at: "2026-11-25T00:00:00Z",
  display: {
    product_name: "测试商品 A", sku_detail_text: "白色x1",
    collection_subject_name: "测试营业执照", settlement_delay_days: 21,
  },
  ...over,
});

const summary = jsonResponse({
  shops: [{
    shop_id: 1, shop_name: "店铺甲", unsettled_amount_cents: 50568, unsettled_count: 2,
    margin_payable_cents: 0, margin_balance_cents: 1000, margin_level: "low",
    margin_synced_at: "2026-11-25T00:00:00Z", synced_at: "2026-11-25T00:00:00Z",
  }],
  total_unsettled_amount_cents: 50568,
  total_unsettled_count: 2,
});

const bills = jsonResponse({
  days: 30,
  shops: [{
    shop_id: 1, source: "upstream", total: 2, error: null,
    fetched_at: "2026-11-25T00:00:00Z",
    items: [
      { amount_cents: 1234, amount_status: "confirmed", amount_field: "settle_amount",
        raw: { bill_type_text: "技术服务费" } },
      { amount_cents: 0, amount_status: "pending", amount_field: null,
        raw: { bill_no: "B0002" } },
    ],
  }],
});

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/fund"]}>
        <Routes>
          <Route path="/fund" element={<FundPage />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("资金聚合页", () => {
  it("默认显示待结算：金额、结算条件与概览", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({
        items: [unsettled()], total: 1, page: 1, page_size: 50,
      }),
    });
    renderPage();
    const tableRow = within(await screen.findByRole("row", { name: /6900000000000000001/ }));
    expect(tableRow.getByText("¥252.84")).toBeInTheDocument();
    expect(tableRow.getByText("确认收货 / 核销后 21 天结算")).toBeInTheDocument();
    expect(await screen.findByText("待结算总额")).toBeInTheDocument();
    expect(screen.getByText("¥505.68")).toBeInTheDocument();
  });

  it("待结算订单号能点击复制", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup(); // setup 会安装自己的剪贴板替身，之后再覆盖
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({ items: [unsettled()], total: 1, page: 1, page_size: 50 }),
    });
    renderPage();
    await user.click(await screen.findByRole("button", { name: "6900000000000000001" }));
    expect(writeText).toHaveBeenCalledWith("6900000000000000001");
    expect(await screen.findByText("已复制")).toBeInTheDocument();
  });

  it("概览三张卡不对应筛选，不可点；金额带 ¥ 与两位小数", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
    });
    renderPage();
    expect(await screen.findByText("待结算总额")).toBeInTheDocument();
    expect(screen.getByText("¥505.68")).toBeInTheDocument();
    expect(screen.getByText("¥10.00")).toBeInTheDocument();
    for (const name of [/待结算总额/, /待结算订单/, /保证金余额/]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("概览读取失败：区块内报错并可重新读取", async () => {
    let fail = true;
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": () => (fail ? errorResponse(500, "Internal", "boom") : summary),
      "GET /api/fund/unsettled": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
    });
    renderPage();
    expect(await screen.findByText("读取资金概览失败，请确认本地服务正常后重试")).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByText("待结算总额")).toBeInTheDocument();
  });

  it("账单金额未校准：一条简短的 warning 提示条，不用徽章装整句话", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/fund/bills": bills,
    });
    renderPage();
    await screen.findByText("待结算总额");
    await userEvent.setup().click(screen.getByRole("button", { name: "账单" }));
    const note = await screen.findByText("部分账单金额待探明");
    expect(note.closest('[role="status"]')).not.toBeNull();
    expect(screen.queryByText(/平台字段名未校准/)).not.toBeInTheDocument();
  });

  it("账单里取数失败的店：短状态「未取到」加原因文字", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/fund/bills": jsonResponse({
        days: 30,
        shops: [{ shop_id: 1, source: "error", total: 0, error: "出口不通，请检查代理是否到期", fetched_at: null, items: null }],
      }),
    });
    renderPage();
    await screen.findByText("待结算总额");
    await userEvent.setup().click(screen.getByRole("button", { name: "账单" }));
    expect(await screen.findByText("未取到")).toBeInTheDocument();
    expect(screen.getByText("出口不通，请检查代理是否到期")).toHaveAttribute("title", "出口不通，请检查代理是否到期");
  });

  it("切到账单：URL 带 tab=bills，未校准金额显示「待探明」", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/bills": bills,
    });
    renderPage();
    await screen.findByText("待结算总额");
    await userEvent.setup().click(screen.getByRole("button", { name: "账单" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("tab=bills"));
    await waitFor(() => expect(screen.getAllByText("待探明").length).toBeGreaterThan(0));
    expect(screen.getByText("¥12.34")).toBeInTheDocument();
    expect(screen.getByText("技术服务费")).toBeInTheDocument();
  });

  it("空状态只写事实，不带操作提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/fund/summary": summary,
      "GET /api/fund/unsettled": jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }),
      "GET /api/fund/bills": jsonResponse({
        days: 30,
        shops: [{ shop_id: 1, source: "upstream", total: 0, error: null, fetched_at: null, items: [] }],
      }),
    });
    renderPage();
    expect(await screen.findByRole("cell", { name: "没有符合条件的待结算订单" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "账单" }));
    expect(await screen.findByText("近 30 天没有账单")).toBeInTheDocument();
  });
});

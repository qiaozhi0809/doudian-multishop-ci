import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
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
});

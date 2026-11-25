import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import DashboardPage from "./index";

const routes = () => ({
  "GET /api/shops": jsonResponse([
    makeShop({ id: 1, name: "店铺甲" }),
    makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired" }),
  ]),
  "GET /api/orders/counts": jsonResponse({
    shops: [
      {
        shop_id: 1,
        source: "upstream",
        counts: { stock_up: 5, exp_ship: 2, ship_delay: 1, in_aftersale: 0 },
        fetched_at: "2026-11-25T01:00:00Z",
      },
      { shop_id: 2, source: "error", error: "上游超时" },
    ],
  }),
  "GET /api/aftersale/counts": jsonResponse({
    shops: [
      {
        shop_id: 1,
        source: "upstream",
        counts: { all_audit: 2, approaching_deadline_audit: 1 },
        pending_total: 3,
        fetched_at: "2026-11-25T01:00:00Z",
      },
    ],
  }),
  "GET /api/fund/summary": jsonResponse({
    shops: [
      {
        shop_id: 1,
        shop_name: "店铺甲",
        unsettled_amount_cents: 123456,
        unsettled_count: 4,
        margin_balance_cents: 100000,
        synced_at: "2026-11-25T00:00:00Z",
      },
    ],
    total_unsettled_amount_cents: 123456,
    total_unsettled_count: 4,
  }),
  "GET /api/catalog/stock/summary": jsonResponse({ total: 10, alarm_count: 2, sold_out_count: 1 }),
  "GET /api/catalog/products/counts": jsonResponse({
    shops: [{ shop_id: 1, source: "upstream", counts: { onsale: 7 }, fetched_at: null }],
  }),
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("仪表盘", () => {
  it("用已有聚合接口展示真实指标、店铺排行与待补说明", async () => {
    mockFetch(routes());
    renderPage();

    const kpi = await screen.findByRole("region", { name: "关键指标" });
    const cardOf = (label: string) => {
      const node = within(kpi).getByText(label);
      return node.closest("article") ?? node.parentElement;
    };
    await waitFor(() => expect(cardOf("在营店铺")).toHaveTextContent("1 / 2"));
    await waitFor(() => expect(cardOf("待发货")).toHaveTextContent("5"));
    await waitFor(() => expect(cardOf("售后待办")).toHaveTextContent("3"));
    await waitFor(() => expect(cardOf("待结算金额")).toHaveTextContent("¥1,234.56"));
    await waitFor(() => expect(cardOf("库存预警")).toHaveTextContent("2"));
    await waitFor(() => expect(cardOf("在售商品")).toHaveTextContent("7"));

    expect(await screen.findByText(/1 家店未取到部分平台数据/)).toBeInTheDocument();
    expect(screen.getByText("店铺乙：上游超时")).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "发货压力" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "待结算分布" })).toBeInTheDocument();

    const rankingTable = await screen.findByRole("table", { name: "店铺排行" });
    const secondRow = within(rankingTable).getByRole("row", { name: /店铺乙/ });
    expect(within(secondRow).getByText("需重新登录")).toBeInTheDocument();
    const firstRow = within(rankingTable).getByRole("row", { name: /店铺甲/ });
    expect(within(firstRow).getByText("正常")).toBeInTheDocument();

    expect(screen.getAllByText("待补").length).toBeGreaterThan(0);
    expect(screen.getByText("支付 GMV")).toBeInTheDocument();
  });

  it("单个数据源失败时只有对应卡片显示暂无，其他指标照常", async () => {
    mockFetch({ ...routes(), "GET /api/catalog/stock/summary": errorResponse(500, "Internal", "boom") });
    renderPage();

    const kpi = await screen.findByRole("region", { name: "关键指标" });
    const cardOf = (label: string) => {
      const node = within(kpi).getByText(label);
      return node.closest("article") ?? node.parentElement;
    };
    await waitFor(() => expect(cardOf("库存预警")).toHaveTextContent("暂无"));
    await waitFor(() => expect(cardOf("售罄")).toHaveTextContent("暂无"));
    await waitFor(() => expect(cardOf("待发货")).toHaveTextContent("5"));
    expect(within(kpi).getAllByRole("button", { name: "重试" })).toHaveLength(2);
  });

  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ ...routes(), "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });
});

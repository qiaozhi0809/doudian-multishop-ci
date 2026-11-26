import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { makeShop, strongOpenSummary } from "@/test/fixtures";
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

function renderPage(entry = "/dashboard") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("仪表盘", () => {
  it("用已有聚合接口展示真实指标与店铺排行，不显示没有数据源的「待补」指标", async () => {
    mockFetch(routes());
    renderPage();

    const kpi = await screen.findByRole("region", { name: "关键指标" });
    const cardOf = (label: string) => {
      const node = within(kpi).getByText(label);
      return node.closest("a");
    };
    await waitFor(() => expect(cardOf("在营店铺")).toHaveTextContent("1 / 2"));
    await waitFor(() => expect(cardOf("待发货")).toHaveTextContent("5"));
    await waitFor(() => expect(cardOf("售后待办")).toHaveTextContent("3"));
    await waitFor(() => expect(cardOf("待结算金额")).toHaveTextContent("¥1,234.56"));
    await waitFor(() => expect(cardOf("库存预警")).toHaveTextContent("2"));
    await waitFor(() => expect(cardOf("在售商品")).toHaveTextContent("7"));

    expect(screen.getByRole("heading", { name: "发货压力" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "待结算分布" })).toBeInTheDocument();

    const rankingTable = await screen.findByRole("table", { name: "店铺排行" });
    const secondRow = within(rankingTable).getByRole("row", { name: /店铺乙/ });
    expect(within(secondRow).getByText("需重新登录")).toBeInTheDocument();
    const firstRow = within(rankingTable).getByRole("row", { name: /店铺甲/ });
    expect(within(firstRow).getByText("正常")).toBeInTheDocument();

    expect(screen.queryByText("待补")).not.toBeInTheDocument();
    expect(screen.queryByText("支付 GMV")).not.toBeInTheDocument();
  });

  it("部分店铺未取到：指标上方一条提示，原因点开才显示，可收起", async () => {
    mockFetch(routes());
    renderPage();
    const title = await screen.findByText("1 家店未取到");
    const kpi = screen.getByRole("region", { name: "关键指标" });
    expect(title.compareDocumentPosition(kpi) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
    expect(screen.queryByText("店铺乙：上游超时")).not.toBeInTheDocument();
    const user = userEvent.setup();
    const toggle = screen.getByRole("button", { name: "查看原因" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getByText("店铺乙：上游超时")).toBeInTheDocument();
    const collapse = screen.getByRole("button", { name: "收起原因" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    await user.click(collapse);
    await waitFor(() => expect(screen.queryByText("店铺乙：上游超时")).not.toBeInTheDocument());
  });

  it("图表副标题只写家数，不写数据来源说明", async () => {
    mockFetch(routes());
    renderPage();
    await waitFor(() => expect(screen.getAllByText("1 家店")).toHaveLength(2));
    expect(screen.queryByText(/平台实时计数|待结算合计/)).not.toBeInTheDocument();
  });

  it("店铺排行的会话状态带状态圆点", async () => {
    mockFetch(routes());
    renderPage();
    const table = await screen.findByRole("table", { name: "店铺排行" });
    for (const name of [/店铺甲/, /店铺乙/]) {
      const cell = within(within(table).getByRole("row", { name })).getByText(/^(正常|需重新登录)$/).closest("td")!;
      expect(cell.querySelector('[aria-hidden="true"] > span')).not.toBeNull();
    }
  });

  it("未取到数据的店已在顶部横条时不再提示", async () => {
    mockFetch({
      ...routes(),
      "GET /api/notifications/summary": jsonResponse(strongOpenSummary([{ shopId: 2, kinds: ["login_expired"] }])),
    });
    renderPage();
    const kpi = await screen.findByRole("region", { name: "关键指标" });
    await waitFor(() => expect(within(kpi).getByText("待发货").closest("a")).toHaveTextContent("5"));
    await waitFor(() => expect(screen.queryByText(/家店未取到/)).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "查看原因" })).not.toBeInTheDocument();
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
  });

  it("单个数据源失败时只有对应卡片显示暂无，其他指标照常", async () => {
    mockFetch({ ...routes(), "GET /api/catalog/stock/summary": errorResponse(500, "Internal", "boom") });
    renderPage();

    const kpi = await screen.findByRole("region", { name: "关键指标" });
    const cardOf = (label: string) => {
      const node = within(kpi).getByText(label);
      return node.closest("a");
    };
    await waitFor(() => expect(cardOf("库存预警")).toHaveTextContent("暂无"));
    await waitFor(() => expect(cardOf("售罄")).toHaveTextContent("暂无"));
    await waitFor(() => expect(cardOf("待发货")).toHaveTextContent("5"));
  });

  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ ...routes(), "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("指标卡可点，跳到对应页面并带上店铺范围", async () => {
    mockFetch(routes());
    renderPage("/dashboard?shops=1");
    const kpi = await screen.findByRole("region", { name: "关键指标" });
    const linkOf = (label: string) => within(kpi).getByText(label).closest("a");
    await waitFor(() => expect(linkOf("保证金余额")).toHaveAttribute("href", "/fund?tab=margin&shops=1"));
    expect(linkOf("在营店铺")).toHaveAttribute("href", "/shops?shops=1");
    expect(linkOf("待发货")).toHaveAttribute("href", "/labeling?shops=1");
    expect(linkOf("24 小时内须发")).toHaveAttribute("href", "/orders?quick=exp_ship&shops=1");
    expect(linkOf("超时未发")).toHaveAttribute("href", "/orders?quick=ship_delay&shops=1");
    expect(linkOf("售后待办")).toHaveAttribute("href", "/aftersale?quick=pending&shops=1");
    expect(linkOf("库存预警")).toHaveAttribute("href", "/stock?quick=alarm&shops=1");
    expect(linkOf("售罄")).toHaveAttribute("href", "/stock?quick=sold_out&shops=1");
    expect(linkOf("在售商品")).toHaveAttribute("href", "/catalog?quick=onsale&shops=1");
  });

  it("指标分三块卡片：发货 / 售后与库存 / 店铺与资金，卡片标题在卡片内，组内从上到下越来越急", async () => {
    mockFetch(routes());
    renderPage();
    const group = async (name: string) =>
      (await within(await screen.findByRole("group", { name })).findAllByRole("link")).map((a) => a.textContent ?? "");
    expect((await group("发货")).map((t) => t.replace(/[\d,.\s/¥]+$/, ""))).toEqual(["待发货", "24 小时内须发", "超时未发"]);
    expect((await group("售后与库存")).map((t) => t.replace(/[\d,.\s/¥]+$/, ""))).toEqual(["售后待办", "库存预警", "售罄"]);
    expect(await group("店铺与资金")).toHaveLength(4);
    const panel = await screen.findByRole("group", { name: "发货" });
    expect(panel).toHaveClass("panel");
    expect(within(panel).getByRole("heading", { name: "发货" })).toHaveClass("section-title");
  });

  it("图表面板没有数据时：标题在卡片上方，卡片里只有一行居中的空提示", async () => {
    mockFetch({
      ...routes(),
      "GET /api/orders/counts": jsonResponse({ shops: [] }),
      "GET /api/fund/summary": jsonResponse({ shops: [], total_unsettled_amount_cents: 0, total_unsettled_count: 0 }),
    });
    renderPage();
    for (const [title, empty] of [["发货压力", "没有待发货积压"], ["待结算分布", "没有待结算金额"]]) {
      const heading = await screen.findByRole("heading", { name: title });
      expect(heading).toHaveClass("section-title");
      const line = await screen.findByText(empty);
      expect(line).toHaveClass("panel-empty");
      expect(line.closest(".panel")).not.toBeNull();
      expect(heading.closest(".panel")).toBeNull();
    }
    expect(screen.getByRole("heading", { name: "店铺排行" })).toHaveClass("section-title");
  });

  it("店铺排行初始不带排序列底色（行已按待发货降序），表头与其他表格一致不分段", async () => {
    mockFetch(routes());
    renderPage();
    const table = await screen.findByRole("table", { name: "店铺排行" });
    expect(table.querySelector("th[data-sorted]")).toBeNull();
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("店铺甲");
  });
});

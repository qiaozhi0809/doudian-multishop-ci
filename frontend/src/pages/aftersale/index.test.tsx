import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop, strongOpenSummary } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import AftersalePage from "./index";

const row = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", after_sale_id: "140000000000000001",
  order_no: "6900000000000000001", type: 1, status: 13, refund_amount_cents: 12800,
  status_deadline: null, apply_time: "2026-11-24T18:40:00Z",
  synced_at: "2026-11-25T00:00:00Z",
  display: {
    status_text: "售后完成", type_text: "退货退款", reason_text: null, buyer_nick: "测*",
    left_node_time: null, platform_intervene: false, detail_link: null, buttons: [],
    order_info: {},
  },
  ...over,
});

const page = (items: unknown[], total = items.length) =>
  jsonResponse({ items, total, page: 1, page_size: 50 });

const counts = jsonResponse({
  shops: [{
    shop_id: 1, source: "upstream", pending_total: 2, error: null,
    counts: { all_audit: 1, approaching_deadline_audit: 1 },
    fetched_at: new Date().toISOString(),
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
      <MemoryRouter initialEntries={["/aftersale"]}>
        <Routes>
          <Route path="/aftersale" element={<AftersalePage />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("售后聚合页", () => {
  it("默认显示待办队列：行内含状态文案、退款金额与截止时间", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/aftersale/todo": page([row()]),
      "GET /api/aftersale/counts": counts,
      "GET /api/aftersale/statuses": jsonResponse({ items: [{ status: 13, label: "待商家处理" }] }),
    });
    renderPage();
    const tableRow = within(await screen.findByRole("row", { name: /140000000000000001/ }));
    expect(tableRow.getByText("售后完成")).toBeInTheDocument();
    expect(tableRow.getByText("¥128.00")).toBeInTheDocument();
    expect(tableRow.getByText("已完结")).toBeInTheDocument();
    expect(screen.getByText("待办售后")).toBeInTheDocument();
  });

  it("未取到计数的店已在顶部横条时不再提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })]),
      "GET /api/aftersale/todo": page([row()]),
      "GET /api/aftersale/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", pending_total: 2, error: null, counts: { all_audit: 1, approaching_deadline_audit: 1 }, fetched_at: null },
          { shop_id: 2, source: "error", pending_total: 0, error: "出口 IP 已变化", counts: {}, fetched_at: null },
        ],
      }),
      "GET /api/aftersale/statuses": jsonResponse({ items: [] }),
      "GET /api/notifications/summary": jsonResponse(strongOpenSummary([{ shopId: 2, kinds: ["egress_changed"] }])),
    });
    renderPage();
    expect(await screen.findByText("待办售后")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/家店未取到/)).not.toBeInTheDocument());
  });

  it("售后单号与订单号都能点击复制；没有订单号显示暂无", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup(); // setup 会安装自己的剪贴板替身，之后再覆盖
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/aftersale/todo": page([row(), row({ id: 2, after_sale_id: "140000000000000002", order_no: null })]),
      "GET /api/aftersale/counts": counts,
      "GET /api/aftersale/statuses": jsonResponse({ items: [] }),
    });
    renderPage();
    const afterSaleNo = await screen.findByRole("button", { name: "140000000000000001" });
    expect(afterSaleNo).toHaveAttribute("title", "点击复制售后单号");
    await user.click(afterSaleNo);
    expect(writeText).toHaveBeenLastCalledWith("140000000000000001");
    const orderNo = screen.getByRole("button", { name: "6900000000000000001" });
    expect(orderNo).toHaveAttribute("title", "点击复制订单号");
    await user.click(orderNo);
    expect(writeText).toHaveBeenLastCalledWith("6900000000000000001");
    const noOrder = within(screen.getByRole("row", { name: /140000000000000002/ }));
    expect(noOrder.getAllByRole("button")).toHaveLength(1);
    expect(noOrder.getAllByRole("cell")[3]).toHaveTextContent("暂无"); // 序号、店铺、售后单号、订单号
  });

  it("平台介入标记带状态圆点", async () => {
    const base = row();
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/aftersale/todo": page([row({ display: { ...base.display, platform_intervene: true } })]),
      "GET /api/aftersale/counts": counts,
      "GET /api/aftersale/statuses": jsonResponse({ items: [] }),
    });
    renderPage();
    const cell = (await screen.findByText("介入")).closest("td");
    expect(cell?.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("部分店铺计数失败：提示 N 家店未取到，可展开原因", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })]),
      "GET /api/aftersale/todo": page([row()]),
      "GET /api/aftersale/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", pending_total: 2, error: null, counts: { all_audit: 1, approaching_deadline_audit: 1 }, fetched_at: null },
          { shop_id: 2, source: "error", pending_total: 0, error: "平台接口报错", counts: {}, fetched_at: null },
        ],
      }),
      "GET /api/aftersale/statuses": jsonResponse({ items: [] }),
    });
    renderPage();
    expect(await screen.findByText("1 家店未取到")).toBeInTheDocument();
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByRole("listitem")).toHaveTextContent("店铺乙：平台接口报错");
  });

  it("切换到全部售后：URL 带 view=all，出现状态筛选", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/aftersale/todo": page([row()], 3),
      "GET /api/aftersale": page([row()], 120),
      "GET /api/aftersale/counts": counts,
      "GET /api/aftersale/statuses": jsonResponse({ items: [{ status: 13, label: "待商家处理" }] }),
    });
    renderPage();
    await screen.findByRole("row", { name: /140000000000000001/ });
    // 切换按钮上带各视图的单数，空的时候也能看出两页不同
    expect(await screen.findByRole("button", { name: "待办队列 3" })).toBeInTheDocument();
    await userEvent.setup().click(await screen.findByRole("button", { name: "全部售后 120" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("view=all"));
    expect(await screen.findByLabelText("售后状态")).toBeInTheDocument();
  });
});

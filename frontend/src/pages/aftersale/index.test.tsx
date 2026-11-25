import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
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

  it("切换到全部售后：URL 带 view=all，出现状态筛选", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/aftersale/todo": page([row()]),
      "GET /api/aftersale": page([row()]),
      "GET /api/aftersale/counts": counts,
      "GET /api/aftersale/statuses": jsonResponse({ items: [{ status: 13, label: "待商家处理" }] }),
    });
    renderPage();
    await screen.findByRole("row", { name: /140000000000000001/ });
    await userEvent.setup().click(screen.getByRole("button", { name: "全部售后" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("view=all"));
    expect(await screen.findByLabelText("售后状态")).toBeInTheDocument();
  });
});

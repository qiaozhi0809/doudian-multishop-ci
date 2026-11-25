import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import LabelingPage from "./index";

const shops = [makeShop({ id: 1, name: "店铺甲" })];

const row = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  shop_id: 1,
  shop_name: "店铺甲",
  order_no: `6900000${id}`,
  status: "pending_label",
  platform_status: 2,
  combine_id: "c1",
  exception_reason: null,
  amount_cents: 123456,
  pay_time: "2026-11-20T01:30:00Z",
  exp_ship_time: "2026-11-22T01:30:00Z",
  items: [
    { sku_order_id: "s1", product_id: "p1", product_name: "商品甲", sku_spec: null, quantity: 1, price_cents: null },
  ],
  blocked_reason: null,
  waybill: null,
  ...over,
});
const page = (items: unknown[], total = items.length) =>
  jsonResponse({ items, total, page: 1, page_size: 50 });

const preview = (over: Record<string, unknown> = {}) => ({
  preview_id: "p1",
  mode: "obtain",
  shops: [
    {
      shop_id: 1,
      shop_name: "店铺甲",
      courier_code: "zhongtong",
      courier_name: "中通快递",
      template_code: "T1",
      ebill_id: "e1",
      net_code: "n1",
      account_balance: 10,
      ready_order_ids: [1],
    },
  ],
  blocked: [],
  shop_errors: [],
  total_ready: 1,
  total_blocked: 0,
  dry_run: false,
  ...over,
});

function renderPage(path = "/labeling") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/labeling" element={<LabelingPage />} />
          <Route path="/shops" element={<h1>店铺页</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

let restoreEvents: () => void;
beforeEach(() => {
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  vi.unstubAllGlobals();
});

describe("打单台", () => {
  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("显示订单行；阻断行不可勾选并显示原因", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([
        row(1),
        row(2, { blocked_reason: "缺少合单 ID（combine_id）", amount_cents: 100 }),
      ]),
    });
    renderPage();
    expect(await screen.findByText("6900000" + "1")).toBeInTheDocument();
    expect(screen.getByText("缺少合单 ID（combine_id）")).toBeInTheDocument();
    expect(screen.getByLabelText("选择订单 69000002")).toBeDisabled();
    expect(screen.getByText("¥1,234.56")).toBeInTheDocument();
    expect(screen.getByText("¥1.00")).toBeInTheDocument();
  });

  it("勾选后打开预览：按店列出快递与账户，确认按钮需要按住", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1)]),
      "POST /api/labels/preview": jsonResponse(preview()),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "打面单" }));

    expect(await screen.findByText("预览：打面单")).toBeInTheDocument();
    expect(screen.getByText(/中通快递/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认打面单/ })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/labels/preview");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ order_ids: [1] });
  });

  it("预览列出被跳过的订单与整店错误", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1), row(2, { blocked_reason: "缺少合单 ID（combine_id）" })]),
      "POST /api/labels/preview": jsonResponse(
        preview({
          total_ready: 1,
          total_blocked: 1,
          blocked: [{ shop_id: 1, shop_name: "店铺甲", order_id: 2, order_no: "69000002", reason: "缺少合单 ID（combine_id）" }],
          shop_errors: [{ shop_id: 1, shop_name: "店铺甲", reason: "没有默认发货地址" }],
        }),
      ),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "打面单" }));
    expect(await screen.findByText(/1 单会被跳过/)).toBeInTheDocument();
    expect(screen.getByText(/69000002：缺少合单 ID/)).toBeInTheDocument();
    expect(screen.getByText(/没有默认发货地址/)).toBeInTheDocument();
  });

  it("演练模式：确认按钮禁用并标注", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1)]),
      "POST /api/labels/preview": jsonResponse(preview({ dry_run: true })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "打面单" }));
    expect(await screen.findByText("演练模式：不能执行写操作")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认打面单/ })).toBeDisabled();
  });

  it("阶段切换写入 URL 并请求对应阶段", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([]),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "已取号" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain(
        "/api/labels/pool?stage=labeled&page=1&page_size=50",
      ),
    );
  });
});

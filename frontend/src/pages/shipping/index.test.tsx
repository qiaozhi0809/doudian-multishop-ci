import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShippingPage from "./index";

const shops = [makeShop({ id: 1, name: "店铺甲" })];

const row = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  shop_id: 1,
  shop_name: "店铺甲",
  order_no: `6900000${id}`,
  status: "printed",
  platform_status: 2,
  amount_cents: 123456,
  pay_time: "2026-11-20T01:30:00Z",
  exp_ship_time: "2026-11-22T01:30:00Z",
  waybill_id: id * 10,
  courier_code: "zhongtong",
  tracking_no: `7920000000000${id}`,
  printed: true,
  ...over,
});

const pool = (items: unknown[], total = items.length) =>
  jsonResponse({ items, total, page: 1, page_size: 50 });

const checkBody = (over: Record<string, unknown> = {}) => ({
  shops: [
    {
      shop_id: 1,
      shop_name: "店铺甲",
      order_nos: ["69000001"],
      total: 1,
      double_check_num: 0,
      double_check_detail: [],
      without_aftersale: [],
      place_holder: null,
    },
  ],
  blocked: [],
  shop_errors: [],
  total_orders: 1,
  double_check_total: 0,
  dry_run: false,
  ...over,
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/shipping"]}>
        <Routes>
          <Route path="/shipping" element={<ShippingPage />} />
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

describe("发货台", () => {
  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("显示待发货订单；缺少运单号的行不可勾选", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/shipping/pool": pool([
        row(1),
        row(2, {
          tracking_no: null, printed: false, status: "label_obtained",
          amount_cents: 100,
        }),
      ]),
    });
    renderPage();
    expect(await screen.findByText("69000001")).toBeInTheDocument();
    expect(screen.getByText("¥1,234.56")).toBeInTheDocument();
    expect(screen.getByLabelText("选择订单 69000002")).toBeDisabled();
  });

  it("勾选后发货前检查：展示检查结果与按住确认按钮", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/shipping/pool": pool([row(1)]),
      "POST /api/shipping/check": jsonResponse(checkBody()),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "发货前检查" }));

    expect(
      await screen.findByRole("button", { name: /按住确认发货/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/通过检查 1 单/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认发货/ })).toBeEnabled();
    const call = fetchMock.mock.calls.find(
      ([u]) => String(u) === "/api/shipping/check",
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ order_ids: [1] });
  });

  it("二次确认项在确认前展示，按钮文案标明已核对", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/shipping/pool": pool([row(1)]),
      "POST /api/shipping/check": jsonResponse(
        checkBody({
          double_check_total: 1,
          shops: [
            {
              shop_id: 1,
              shop_name: "店铺甲",
              order_nos: ["69000001"],
              total: 1,
              double_check_num: 1,
              double_check_detail: [
                { title: "请确认发货信息", message: "买家收货地址异常" },
              ],
              without_aftersale: [],
              place_holder: null,
            },
          ],
        }),
      ),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "发货前检查" }));
    expect(await screen.findByText(/请确认发货信息：买家收货地址异常/)).toBeInTheDocument();
    expect(screen.getByText("平台要求二次确认")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /按住确认发货（已核对二次确认项）/ }),
    ).toBeInTheDocument();
  });

  it("不可发货订单与整店错误都列在检查结果里", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/shipping/pool": pool([row(1)]),
      "POST /api/shipping/check": jsonResponse(
        checkBody({
          total_orders: 0,
          shops: [],
          blocked: [
            { order_id: 2, order_no: "69000002", shop_name: "店铺甲", reason: "没有有效面单" },
          ],
          shop_errors: [
            { shop_id: 1, shop_name: "店铺甲", reason: "没有默认发货地址" },
          ],
        }),
      ),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "发货前检查" }));
    expect(await screen.findByText(/没有有效面单/)).toBeInTheDocument();
    expect(screen.getByText(/没有默认发货地址/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认发货/ })).toBeDisabled();
  });

  it("演练模式：提示只记录请求，确认按钮标注（演练）且仍可提交", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/shipping/pool": pool([row(1)]),
      "POST /api/shipping/check": jsonResponse(checkBody({ dry_run: true })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "发货前检查" }));
    expect(await screen.findByText(/演练模式：本次只记录请求/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认发货（演练）/ })).toBeEnabled();
  });
});

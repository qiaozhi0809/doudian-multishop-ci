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

const printStatus = (available = true) => ({
  available,
  printers: available ? ["Printer A"] : [],
  default_printer: available ? "Printer A" : null,
  error: available ? null : "请先启动抖店官方打印组件",
  checked_at: "2026-11-25T00:00:00Z",
});

/** 打印组件状态在每个打单台页面都会探测一次，所有用例都要登记。 */
const printRoutes = (available = true) => ({
  "GET /api/print/status": jsonResponse(printStatus(available)),
});

const labeledRow = (id: number, over: Record<string, unknown> = {}) =>
  row(id, {
    status: "label_obtained",
    waybill: {
      id: id * 10,
      courier_code: "zhongtong",
      waybill_no: `7920000000000${id}`,
      status: "active",
      seq: 1,
      obtained_at: "2026-11-20T02:00:00Z",
      template_code: "T1",
    },
    ...over,
  });

const printRow = (waybillId: number, job: Record<string, unknown> | null) => ({
  waybill_id: waybillId,
  waybill_no: `7920000000000${waybillId / 10}`,
  waybill_status: "active",
  has_print_data: true,
  job:
    job === null
      ? null
      : {
          id: 100,
          waybill_id: waybillId,
          printer_name: "Printer A",
          status: "queued",
          result_code: null,
          result_detail: null,
          attempts: 0,
          created_at: "2026-11-25T00:00:00Z",
          finished_at: null,
          ...job,
        },
});

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

describe("打单发货", () => {
  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ ...printRoutes(), "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("显示订单行；阻断行不可勾选并显示原因", async () => {
    mockFetch({
      ...printRoutes(),
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
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1)]),
      "POST /api/labels/preview": jsonResponse(preview()),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "打单" }));

    expect(await screen.findByText("预览：打单")).toBeInTheDocument();
    expect(screen.getByText(/中通快递/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认打单/ })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/labels/preview");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ order_ids: [1] });
  });

  it("预览列出被跳过的订单与整店错误", async () => {
    mockFetch({
      ...printRoutes(),
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
    await user.click(screen.getByRole("button", { name: "打单" }));
    expect(await screen.findByText(/1 单会被跳过/)).toBeInTheDocument();
    expect(screen.getByText(/69000002：缺少合单 ID/)).toBeInTheDocument();
    expect(screen.getByText(/没有默认发货地址/)).toBeInTheDocument();
  });

  it("演练模式：提示只记录请求，确认按钮标注（演练）且仍可提交", async () => {
    mockFetch({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1)]),
      "POST /api/labels/preview": jsonResponse(preview({ dry_run: true })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    await user.click(screen.getByRole("button", { name: "打单" }));
    expect(await screen.findByText(/演练模式：本次只记录请求/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /按住确认打单（演练）/ })).toBeEnabled();
  });

  it("阶段切换写入 URL 并请求对应阶段", async () => {
    const fetchMock = mockFetch({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([]),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "待发货" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain(
        "/api/labels/pool?stage=labeled&page=1&page_size=50",
      ),
    );
  });

  it("待发货阶段：勾选后按面单提交打印任务", async () => {
    const fetchMock = mockFetch({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([labeledRow(1)]),
      "GET /api/print/waybills": jsonResponse({ items: [printRow(10, null)] }),
      "POST /api/print/jobs": jsonResponse({ job_ids: [100], waybill_ids: [10] }, 202),
    });
    renderPage("/labeling?stage=labeled");
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    const button = screen.getByRole("button", { name: "打印面单" });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/print/jobs");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ waybill_ids: [10] });
  });

  it("组件未启动：打印按钮置灰并提示先启动组件", async () => {
    mockFetch({
      ...printRoutes(false),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([labeledRow(1)]),
      "GET /api/print/waybills": jsonResponse({ items: [printRow(10, null)] }),
    });
    renderPage("/labeling?stage=labeled");
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("选择订单 69000001"));
    const button = screen.getByRole("button", { name: "打印面单" });
    await waitFor(() => expect(button).toHaveAttribute("title", "请先启动抖店官方打印组件"));
    expect(button).toBeDisabled();
    expect(await screen.findByText(/打印组件未启动/)).toBeInTheDocument();
  });

  it("打印任务状态显示在面单列与汇总里", async () => {
    mockFetch({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([labeledRow(1)]),
      "GET /api/print/waybills": jsonResponse({
        items: [printRow(10, { status: "queued", attempts: 0 })],
      }),
    });
    renderPage("/labeling?stage=labeled");
    expect(await screen.findByText("打印中")).toBeInTheDocument();
    expect(await screen.findByText("打印中：剩余 1 张面单")).toBeInTheDocument();
  });

  describe("待发货阶段：发货（原发货台）", () => {
    const shipCheck = (over: Record<string, unknown> = {}) => ({
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
    const shipRoutes = (check: unknown) => ({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([labeledRow(1)]),
      "GET /api/print/waybills": jsonResponse({ items: [printRow(10, null)] }),
      "POST /api/shipping/check": jsonResponse(check),
    });
    const openCheck = async () => {
      renderPage("/labeling?stage=labeled");
      const user = userEvent.setup();
      await user.click(await screen.findByLabelText("选择订单 69000001"));
      await user.click(screen.getByRole("button", { name: "发货" }));
    };

    it("待打单阶段不显示发货，待发货阶段不显示打单", async () => {
      mockFetch(shipRoutes(shipCheck()));
      renderPage("/labeling?stage=labeled");
      expect(await screen.findByRole("button", { name: "发货" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "打单" })).not.toBeInTheDocument();
    });

    it("勾选后发货：先做发货前检查，展示结果与按住确认按钮", async () => {
      const fetchMock = mockFetch(shipRoutes(shipCheck()));
      await openCheck();
      expect(await screen.findByRole("button", { name: /按住确认发货/ })).toBeEnabled();
      expect(screen.getByText(/通过检查 1 单/)).toBeInTheDocument();
      const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/shipping/check");
      expect(JSON.parse(String(call?.[1]?.body))).toEqual({ order_ids: [1] });
    });

    it("二次确认项在确认前展示，按钮文案标明已核对", async () => {
      mockFetch(
        shipRoutes(
          shipCheck({
            double_check_total: 1,
            shops: [
              {
                shop_id: 1,
                shop_name: "店铺甲",
                order_nos: ["69000001"],
                total: 1,
                double_check_num: 1,
                double_check_detail: [{ title: "请确认发货信息", message: "买家收货地址异常" }],
                without_aftersale: [],
                place_holder: null,
              },
            ],
          }),
        ),
      );
      await openCheck();
      expect(await screen.findByText(/请确认发货信息：买家收货地址异常/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /按住确认发货（已核对二次确认项）/ })).toBeInTheDocument();
    });

    it("不可发货订单与整店错误都列在检查结果里，不能确认", async () => {
      mockFetch(
        shipRoutes(
          shipCheck({
            total_orders: 0,
            shops: [],
            blocked: [{ order_id: 2, order_no: "69000002", shop_name: "店铺甲", reason: "没有有效面单" }],
            shop_errors: [{ shop_id: 1, shop_name: "店铺甲", reason: "没有默认发货地址" }],
          }),
        ),
      );
      await openCheck();
      expect(await screen.findByText(/没有有效面单/)).toBeInTheDocument();
      expect(screen.getByText(/没有默认发货地址/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /按住确认发货/ })).toBeDisabled();
    });

    it("演练模式：确认按钮标注（演练）且仍可提交", async () => {
      mockFetch(shipRoutes(shipCheck({ dry_run: true })));
      await openCheck();
      expect(await screen.findByText(/演练模式：本次只记录请求/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /按住确认发货（演练）/ })).toBeEnabled();
    });
  });
});

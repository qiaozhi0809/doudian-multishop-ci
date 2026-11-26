import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { labeledRow, page, preview, printRoutes, printRow, reasonOf, renderPage, row, shops } from "./labeling-test-fixtures";

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

  it("序号在勾选列之后、翻页连续；点支付时间表头带排序请求，再点改降序", async () => {
    const fetchMock = mockFetch({
      ...printRoutes(),
      "GET /api/shops": jsonResponse(shops),
      "GET /api/labels/pool": page([row(1), row(2)], 120, 2),
    });
    renderPage("/labeling?page=2");
    const first = await screen.findByRole("row", { name: /69000001/ });
    expect(within(first).getAllByRole("cell")[1]).toHaveTextContent("51");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "支付时间" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain(
        "/api/labels/pool?stage=pending&page=1&page_size=50&sort=pay_time&order=asc",
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("columnheader", { name: "支付时间" })).toHaveAttribute("aria-sort", "ascending"),
    );
    await user.click(screen.getByRole("button", { name: "支付时间" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain(
        "/api/labels/pool?stage=pending&page=1&page_size=50&sort=pay_time&order=desc",
      ),
    );
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
    expect(await screen.findByText(/打印组件未启动/)).toBeInTheDocument();
    const gated = screen.getByRole("button", { name: "打印面单" });
    expect(gated).not.toHaveAttribute("title");
    expect(await reasonOf(gated)).toContain("请先启动抖店官方打印组件");
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

});

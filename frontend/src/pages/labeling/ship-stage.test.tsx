import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { labeledRow, page, printRoutes, printRow, renderPage, shops } from "./labeling-test-fixtures";

let restoreEvents: () => void;
beforeEach(() => {
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  vi.unstubAllGlobals();
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

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import {
  hang,
  labeledRow,
  page,
  preview,
  printRoutes,
  printRow,
  reasonOf,
  renderPage,
  row,
  shops,
} from "./labeling-test-fixtures";

let restoreEvents: () => void;
beforeEach(() => {
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  vi.unstubAllGlobals();
});

const pendingRoutes = () => ({
  ...printRoutes(),
  "GET /api/shops": jsonResponse(shops),
  "GET /api/labels/pool": page([row(1)]),
});
const labeledRoutes = (available = true) => ({
  ...printRoutes(available),
  "GET /api/shops": jsonResponse(shops),
  "GET /api/labels/pool": page([labeledRow(1)]),
  "GET /api/print/waybills": jsonResponse({ items: [printRow(10, null)] }),
});
const select = async () => {
  const user = userEvent.setup();
  await user.click(await screen.findByLabelText("选择订单 69000001"));
  return user;
};
const button = (name: string) => screen.getByRole("button", { name });
const calls = (fetchMock: ReturnType<typeof mockFetch>, url: string) =>
  fetchMock.mock.calls.filter(([u]) => String(u) === url).length;
/** 按住确认按钮：按下回车直到进度走满（默认 1.2 秒）。 */
const hold = (name: RegExp) => fireEvent.keyDown(screen.getByRole("button", { name }), { key: "Enter" });

describe("工具栏按钮禁用时说明原因", () => {
  it("待打单：没勾选时两个按钮都提示先勾选订单；勾选后可点且不再包提示层", async () => {
    mockFetch(pendingRoutes());
    renderPage();
    await screen.findByLabelText("选择订单 69000001");
    for (const name of ["打单", "打单并发货"]) {
      expect(await reasonOf(button(name))).toContain("先勾选订单");
    }
    await select();
    for (const name of ["打单", "打单并发货"]) {
      expect(button(name)).toBeEnabled();
      expect(button(name).parentElement).not.toHaveAttribute("tabindex");
    }
  });

  it("待发货：没勾选时发货、打印面单、作废面单都提示先勾选订单", async () => {
    mockFetch(labeledRoutes());
    renderPage("/labeling?stage=labeled");
    await screen.findByLabelText("选择订单 69000001");
    await waitFor(async () => expect(await reasonOf(button("打印面单"))).toContain("先勾选订单"));
    for (const name of ["发货", "作废面单"]) {
      expect(await reasonOf(button(name))).toContain("先勾选订单");
    }
  });

  it("打单进行中：打单按钮转圈但不置灰、重复点击不再请求，另一个按钮说明原因", async () => {
    const fetchMock = mockFetch(pendingRoutes());
    hang(fetchMock, "/api/labels/preview");
    renderPage();
    const user = await select();
    await user.click(button("打单"));
    await waitFor(() => expect(button("打单")).toHaveAttribute("aria-busy", "true"));
    expect(button("打单")).not.toHaveAttribute("disabled");
    expect(await reasonOf(button("打单并发货"))).toContain("有操作进行中");
    await user.click(button("打单"));
    expect(calls(fetchMock, "/api/labels/preview")).toBe(1);
  });

  it("发货检查进行中：发货按钮转圈但不置灰、重复点击不再请求", async () => {
    const fetchMock = mockFetch(labeledRoutes());
    hang(fetchMock, "/api/shipping/check");
    renderPage("/labeling?stage=labeled");
    const user = await select();
    await user.click(button("发货"));
    await waitFor(() => expect(button("发货")).toHaveAttribute("aria-busy", "true"));
    expect(button("发货")).not.toHaveAttribute("disabled");
    await user.click(button("发货"));
    expect(calls(fetchMock, "/api/shipping/check")).toBe(1);
  });

  it("打印提交中：打印按钮转圈但不置灰、重复点击不再请求", async () => {
    const fetchMock = mockFetch(labeledRoutes());
    hang(fetchMock, "/api/print/jobs");
    renderPage("/labeling?stage=labeled");
    const user = await select();
    await waitFor(() => expect(button("打印面单")).toBeEnabled());
    await user.click(button("打印面单"));
    await waitFor(() => expect(button("打印面单")).toHaveAttribute("aria-busy", "true"));
    expect(button("打印面单")).not.toHaveAttribute("disabled");
    await user.click(button("打印面单"));
    expect(calls(fetchMock, "/api/print/jobs")).toBe(1);
  });
});

describe("表格单元格", () => {
  it("查看收件人是次要小按钮", async () => {
    mockFetch(pendingRoutes());
    renderPage();
    const action = await screen.findByRole("button", { name: "查看收件人" });
    expect(action.className).toMatch(/secondary/);
    expect(action.className).toMatch(/\bsm\b|_sm_/);
  });

  it("支付时间悬停显示完整时间", async () => {
    mockFetch(pendingRoutes());
    renderPage();
    expect(await screen.findByTitle("2026-11-20 09:30")).toBeInTheDocument();
  });

  it("无打印数据的悬停说明是一句短话", async () => {
    mockFetch({
      ...labeledRoutes(),
      "GET /api/print/waybills": jsonResponse({ items: [{ ...printRow(10, null), has_print_data: false }] }),
    });
    renderPage("/labeling?stage=labeled");
    expect(await screen.findByText("无打印数据")).toHaveAttribute("title", "打印时先补打，失败到抖店后台补打");
  });
});

describe("提交后的提示", () => {
  const openAndHold = async (executeRoute: Response | null) => {
    const fetchMock = mockFetch({
      ...pendingRoutes(),
      "POST /api/labels/preview": jsonResponse(preview()),
      ...(executeRoute ? { "POST /api/labels/execute": executeRoute } : {}),
    });
    if (!executeRoute) hang(fetchMock, "/api/labels/execute");
    renderPage();
    const user = await select();
    await user.click(button("打单"));
    await screen.findByText("预览：打单");
    hold(/按住确认打单/);
  };

  it("按住完成后写明做了什么", async () => {
    await openAndHold(null);
    expect(await screen.findByRole("button", { name: "已发起打单" }, { timeout: 4000 })).toBeInTheDocument();
  });

  it("提交失败：原因只显示在对话框里，按钮复位可以再按", async () => {
    await openAndHold(errorResponse(422, "InvalidRequest", "预览已过期，请重新预览"));
    const dialog = await screen.findByRole("dialog", { name: "预览：打单" });
    expect(await within(dialog).findByText("预览已过期，请重新预览", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /按住确认打单/ })).toBeEnabled();
    expect(screen.getAllByText("预览已过期，请重新预览")).toHaveLength(1);
  });

  it("发货按住完成后写明已发起发货", async () => {
    const fetchMock = mockFetch({
      ...labeledRoutes(),
      "POST /api/shipping/check": jsonResponse({
        shops: [], blocked: [], shop_errors: [], total_orders: 1, double_check_total: 0, dry_run: false,
      }),
    });
    hang(fetchMock, "/api/shipping/ship");
    renderPage("/labeling?stage=labeled");
    const user = await select();
    await user.click(button("发货"));
    await screen.findByText("发货前检查");
    hold(/按住确认发货/);
    expect(await screen.findByRole("button", { name: "已发起发货" }, { timeout: 4000 })).toBeInTheDocument();
  });

  it("演练模式执行后页内只留一句话", async () => {
    await openAndHold(jsonResponse({ preview_id: "p1", simulated: true }, 202));
    expect(await screen.findByText("已记录请求，未真实执行", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByText(/演练模式/)).not.toBeInTheDocument();
    expect(screen.queryByText(/关闭演练模式后/)).not.toBeInTheDocument();
  });

  it("演练模式打印用同一句话", async () => {
    mockFetch({
      ...labeledRoutes(),
      "POST /api/print/jobs": jsonResponse({ job_ids: [], waybill_ids: [10], simulated: true }, 202),
    });
    renderPage("/labeling?stage=labeled");
    const user = await select();
    await waitFor(() => expect(button("打印面单")).toBeEnabled());
    await user.click(button("打印面单"));
    expect(await screen.findByText("已记录请求，未真实执行")).toBeInTheDocument();
    expect(screen.queryByText(/演练模式/)).not.toBeInTheDocument();
  });
});

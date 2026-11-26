import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { finding, findingsPage, renderPage, shops, started } from "./reconcile-test-fixtures";

let restoreEvents: () => void;
beforeEach(() => {
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  vi.unstubAllGlobals();
});

describe("对账页", () => {
  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("展示三类异常与运单对比；上次检查正常时页内不放结果条", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([
        finding(1),
        finding(2, {
          kind: "waybill_mismatch",
          kind_title: "运单号不一致",
          local_status: 3,
          local_tracking_no: "OLD-TRACKING",
          platform_tracking_no: "NEW-TRACKING",
        }),
        finding(3, {
          kind: "local_shipped_platform_not",
          kind_title: "本地已发货、平台未发货",
          local_status: 3,
          platform_status: 2,
          local_tracking_no: "79200000000003",
          platform_tracking_no: null,
        }),
      ]),
    });
    renderPage();
    expect(await screen.findByText("平台已发货、本地未记录")).toBeInTheDocument();
    expect(screen.getByText("运单号不一致")).toBeInTheDocument();
    expect(screen.getByText("本地已发货、平台未发货")).toBeInTheDocument();
    expect(screen.getByText("OLD-TRACKING → NEW-TRACKING")).toBeInTheDocument();
    expect(screen.queryByText(/扫描 12 单/)).not.toBeInTheDocument();
    expect(screen.getByText(/3 → 2/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "69000001" })).toHaveAttribute("title", "点击复制订单号");
  });

  it("立即检查提交 30 天窗口并刷新结果", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
      "POST /api/reconcile/run": started(),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "立即检查" }));
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/reconcile/run");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ window_days: 30 });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([u]) =>
          String(u).startsWith("/api/reconcile/findings"),
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("标记已处理后提交 PATCH", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([finding(1)]),
      "PATCH /api/reconcile/findings/1": jsonResponse(finding(1, { status: "handled" })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "标记已处理" }));
    const call = fetchMock.mock.calls.find(
      ([u]) => String(u) === "/api/reconcile/findings/1",
    );
    expect(call?.[1]?.method).toBe("PATCH");
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ status: "handled" });
  });

  it("异常类型筛选写入请求参数", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "运单不一致" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.map(([u]) => String(u)).some((u) =>
          u.includes("kind=waybill_mismatch"),
        ),
      ).toBe(true),
    );
  });

  it("还没有检查记录时不显示说明条，表格内显示空提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([], 0, null as never),
    });
    renderPage();
    expect(await screen.findByRole("cell", { name: "没有符合条件的发货异常" })).toBeInTheDocument();
    expect(screen.queryByText(/检查记录/)).not.toBeInTheDocument();
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import ReconcilePage from "./index";

const shops = [makeShop({ id: 1, name: "店铺甲" })];

const run = (over: Record<string, unknown> = {}) => ({
  id: 1,
  run_id: "r1",
  status: "success",
  shop_ids: [1],
  window_days: 30,
  started_at: "2026-11-25T00:00:00Z",
  finished_at: "2026-11-25T00:01:00Z",
  scanned: 12,
  finding_count: 2,
  error: null,
  ...over,
});

const finding = (id: number, over: Record<string, unknown> = {}) => ({
  id,
  run_id: "r1",
  shop_id: 1,
  shop_name: "店铺甲",
  shop_order_id: `6900000${id}`,
  kind: "platform_shipped_local_not",
  kind_title: "平台已发货、本地未记录",
  local_status: null,
  platform_status: 3,
  local_tracking_no: null,
  platform_tracking_no: `7920000000000${id}`,
  local_company_code: null,
  platform_company_code: "zhongtong",
  detail: "平台已发货，快照无记录",
  status: "open",
  created_at: "2026-11-25T00:01:00Z",
  handled_at: null,
  ...over,
});

const findingsPage = (items: unknown[], total = items.length, runRow = run()) =>
  jsonResponse({ items, total, page: 1, page_size: 50, run: runRow });

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/reconcile"]}>
        <Routes>
          <Route path="/reconcile" element={<ReconcilePage />} />
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

describe("对账页", () => {
  it("还没有店铺时引导去店铺页", async () => {
    mockFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
  });

  it("展示三类异常、运单对比与本次对账摘要", async () => {
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
    expect(screen.getByText(/扫描 12 单，发现 2 条异常/)).toBeInTheDocument();
    expect(screen.getByText(/3 → 2/)).toBeInTheDocument();
  });

  it("立即对账提交 30 天窗口并刷新结果", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
      "POST /api/reconcile/run": jsonResponse(
        {
          run_id: "r2",
          status: "running",
          shop_ids: [1],
          window_days: 30,
          started_at: "2026-11-25T00:02:00Z",
        },
        202,
      ),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "立即对账" }));
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
});

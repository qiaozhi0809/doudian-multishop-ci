import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, type mockFetch } from "@/test/mock-fetch";
import { NoticeProvider } from "@/components/custom/notice/notice";
import ReconcilePage from "./index";

/** 发货异常页测试共用的数据与渲染（index.test / controls.test）。 */
export const shops = [makeShop({ id: 1, name: "店铺甲" })];

export const run = (over: Record<string, unknown> = {}) => ({
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

export const finding = (id: number, over: Record<string, unknown> = {}) => ({
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

export const findingsPage = (items: unknown[], total = items.length, runRow = run()) =>
  jsonResponse({ items, total, page: 1, page_size: 50, run: runRow });

export const started = (runId = "r2") =>
  jsonResponse(
    { run_id: runId, status: "running", shop_ids: [1], window_days: 30, started_at: "2026-11-25T00:02:00Z" },
    202,
  );
/** 右下角浮动提示区。 */
export const toasts = () => within(screen.getByLabelText("操作提示"));
export const posts = (fetchMock: ReturnType<typeof mockFetch>) =>
  fetchMock.mock.calls.filter(([u]) => String(u) === "/api/reconcile/run").length;

export function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/reconcile"]}>
        <NoticeProvider>
          <Routes>
            <Route path="/reconcile" element={<ReconcilePage />} />
            <Route path="/shops" element={<h1>店铺页</h1>} />
          </Routes>
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

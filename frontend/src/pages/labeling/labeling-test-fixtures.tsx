import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { makeShop } from "@/test/fixtures";
import { jsonResponse } from "@/test/mock-fetch";
import LabelingPage from "./index";

/** 打单发货页测试共用的数据与渲染（index.test / ship-stage.test）。 */
export const shops = [makeShop({ id: 1, name: "店铺甲" })];

export const row = (id: number, over: Record<string, unknown> = {}) => ({
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
export const page = (items: unknown[], total = items.length, current = 1) =>
  jsonResponse({ items, total, page: current, page_size: 50 });

export const printStatus = (available = true) => ({
  available,
  printers: available ? ["Printer A"] : [],
  default_printer: available ? "Printer A" : null,
  error: available ? null : "请先启动抖店官方打印组件",
  checked_at: "2026-11-25T00:00:00Z",
});

/** 打印组件状态在每个打单台页面都会探测一次，所有用例都要登记。 */
export const printRoutes = (available = true) => ({
  "GET /api/print/status": jsonResponse(printStatus(available)),
});

export const labeledRow = (id: number, over: Record<string, unknown> = {}) =>
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

export const printRow = (waybillId: number, job: Record<string, unknown> | null) => ({
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

export const preview = (over: Record<string, unknown> = {}) => ({
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

export function renderPage(path = "/labeling") {
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

import type { components } from "@/lib/api-types";

export type StockRow = components["schemas"]["StockRow"];
export type StockSummary = components["schemas"]["StockSummary"];
export type WarehousesResponse = components["schemas"]["WarehousesResponse"];
export type WarehouseItem = components["schemas"]["WarehouseItem"];

export const PAGE_SIZE = 50;
export const STOCK_VIEWS = [
  { value: "all", label: "全部库存" },
  { value: "alarm", label: "只看预警" },
] as const;
export type StockView = (typeof STOCK_VIEWS)[number]["value"];

export function isStockView(value: string | null): value is StockView {
  return value === "all" || value === "alarm";
}

export type StockBadgeTone = "success" | "warning" | "danger" | "neutral";

/** 预警优先于售罄：平台把缺货商品单独计数，但两者都可能出现在同一行。 */
export function stockBadge(row: StockRow): { label: string; tone: StockBadgeTone } {
  if (row.is_alarming) return { label: "预警", tone: "danger" };
  if (row.total_stock_num === 0) return { label: "售罄", tone: "warning" };
  return { label: "正常", tone: "success" };
}

export interface ShopWarehouses {
  shopId: number;
  items: WarehouseItem[];
  error: string | null;
}

/** 每店的仓库列表与失败原因（上游请求，单店失败隔离）。 */
export function groupWarehouses(resp: WarehousesResponse): ShopWarehouses[] {
  return resp.shops.map((shop) => ({
    shopId: shop.shop_id,
    items: shop.items ?? [],
    error: shop.source === "upstream" ? null : shop.error ?? "原因未知",
  }));
}

export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PAGE_SIZE));
}

import type { components } from "@/lib/api-types";

export type StockRow = components["schemas"]["StockRow"];
export type StockSummary = components["schemas"]["StockSummary"];
export type WarehousesResponse = components["schemas"]["WarehousesResponse"];
export type WarehouseItem = components["schemas"]["WarehouseItem"];

export const PAGE_SIZE = 50;
/** 可排序的列，与后端 /api/catalog/stock 的 sort 白名单一致；默认按总库存升序（缺货的在前）。 */
export const STOCK_SORT_KEYS = [
  "shop_name", "total_stock_num", "spot_stock_num", "future_stock_num",
  "total_occupied_stock_num", "total_unoccupied_stock_num", "status", "synced_at",
] as const;
/** 计数卡快捷筛选，与后端 /api/catalog/stock 的 quick 白名单一致；「商品数」卡 = 清除筛选。 */
export const STOCK_QUICK_KEYS = ["alarm", "sold_out"] as const;
export type StockQuick = (typeof STOCK_QUICK_KEYS)[number];

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

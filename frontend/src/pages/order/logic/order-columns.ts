import type { components } from "@/lib/api-types";

type OrderRow = components["schemas"]["OrderRow"];
export type LocalStatus = OrderRow["status"];

export { localStatusBadge, LOCAL_STATUS_OPTIONS, isLocalStatus, platformStatusText } from "@/lib/order-status";

export const PAGE_SIZE = 50;
export const pageCount = (total: number) => Math.ceil(total / PAGE_SIZE);

/** 商品摘要：首个商品名 + 「等 N 件」（N 为商品行数）。 */
export function itemSummary(items: OrderRow["items"]): string {
  if (items.length === 0) return "暂无";
  const first = items[0].product_name || "暂无";
  return items.length > 1 ? `${first} 等 ${items.length} 件` : first;
}

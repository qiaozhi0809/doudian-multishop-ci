import type { components } from "@/lib/api-types";
import { EMPTY_TEXT } from "@/lib/empty-text";

type OrderRow = components["schemas"]["OrderRow"];
export type LocalStatus = OrderRow["status"];

export { localStatusBadge, LOCAL_STATUS_OPTIONS, isLocalStatus, platformStatusText } from "@/lib/order-status";

export const PAGE_SIZE = 50;
/** 可排序的列，与后端 /api/orders 的 sort 白名单一致；默认按支付时间倒序。 */
/** 计数卡快捷筛选，与后端 /api/orders 的 quick 白名单一致（键名同计数字段）。 */
export const ORDER_QUICK_KEYS = ["stock_up", "exp_ship", "ship_delay", "in_aftersale"] as const;
export const ORDER_SORT_KEYS = ["shop_name", "platform_status", "status", "amount_cents", "pay_time", "exp_ship_time"] as const;

/** 商品摘要：首个商品名 + 「等 N 件」（N 为商品行数）。 */
export function itemSummary(items: OrderRow["items"]): string {
  if (items.length === 0) return EMPTY_TEXT;
  const first = items[0].product_name || EMPTY_TEXT;
  return items.length > 1 ? `${first} 等 ${items.length} 件` : first;
}

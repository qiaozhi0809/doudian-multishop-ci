import type { KpiTone } from "@/lib/kpi-tone";
import type { components } from "@/lib/api-types";

type OrderCountsResponse = components["schemas"]["OrderCountsResponse"];
type OrderCounts = components["schemas"]["OrderCounts"];
export type CountKey = keyof OrderCounts;

/** 平台口径的四项计数（api/order-page.md C.1）。只展示计数，不用于筛选列表。 */
export const COUNT_ITEMS: { key: CountKey; label: string; tone: KpiTone }[] = [
  { key: "stock_up", label: "待发货", tone: "info" },
  { key: "exp_ship", label: "24 小时内须发", tone: "warning" },
  { key: "ship_delay", label: "超时未发", tone: "danger" },
  { key: "in_aftersale", label: "售后中", tone: "violet" },
];

export interface AggregatedCounts {
  totals: Record<CountKey, number>;
  failedShopIds: number[];
  failures: { shopId: number; error: string | null }[];
  /** 是否至少有一家店取到了数据 */
  hasData: boolean;
  /** 各店数据时间中最早的一个（后端按店缓存 60 秒） */
  fetchedAt: string | null;
}

/** 只合计 `source === "upstream"` 且有数据的店；取不到的店单独列出，不能当 0 静默合计。 */
export function aggregateCounts(resp: OrderCountsResponse): AggregatedCounts {
  const totals: Record<CountKey, number> = { stock_up: 0, exp_ship: 0, ship_delay: 0, in_aftersale: 0 };
  const failures: AggregatedCounts["failures"] = [];
  let hasData = false;
  let fetchedAt: string | null = null;

  for (const shop of resp.shops) {
    if (shop.source !== "upstream" || !shop.counts) {
      failures.push({ shopId: shop.shop_id, error: shop.error ?? null });
      continue;
    }
    hasData = true;
    for (const { key } of COUNT_ITEMS) totals[key] += shop.counts[key];
    if (shop.fetched_at && (fetchedAt === null || new Date(shop.fetched_at) < new Date(fetchedAt))) {
      fetchedAt = shop.fetched_at;
    }
  }
  return { totals, failedShopIds: failures.map((f) => f.shopId), failures, hasData, fetchedAt };
}

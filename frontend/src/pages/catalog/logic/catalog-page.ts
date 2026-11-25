import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";

export type ProductRow = components["schemas"]["ProductRow"];
export type ProductCountsResponse = components["schemas"]["ProductCountsResponse"];
export type ProductGroupsResponse = components["schemas"]["ProductGroupsResponse"];
export type GroupItem = components["schemas"]["GroupItem"];

export const PAGE_SIZE = 50;
export const PRODUCT_COUNT_ITEMS = [
  // 第一行正常状态，第二行要处理的；红色集中在右下角
  { key: "onsale", label: "在售", tone: "success" },
  { key: "draft", label: "草稿", tone: "neutral" },
  { key: "audit", label: "审核中", tone: "info" },
  { key: "sell_out_new", label: "售罄", tone: "warning" },
  { key: "unpass", label: "未通过", tone: "danger" },
  { key: "forbidden", label: "禁售 / 下架", tone: "danger" },
] as const;
export type ProductCountKey = (typeof PRODUCT_COUNT_ITEMS)[number]["key"];

export interface AggregatedProductCounts {
  totals: Record<ProductCountKey, number>;
  failedShopIds: number[];
  failures: { shopId: number; error: string | null }[];
  hasData: boolean;
  fetchedAt: string | null;
}

/** 只合计 `source === "upstream"` 的店；取不到的店单独列出，不当 0 静默合计。 */
export function aggregateProductCounts(resp: ProductCountsResponse): AggregatedProductCounts {
  const totals = Object.fromEntries(
    PRODUCT_COUNT_ITEMS.map((item) => [item.key, 0]),
  ) as Record<ProductCountKey, number>;
  const failedShopIds: number[] = [];
  const failures: { shopId: number; error: string | null }[] = [];
  let hasData = false;
  let fetchedAt: string | null = null;

  for (const shop of resp.shops) {
    if (shop.source !== "upstream" || !shop.counts) {
      failedShopIds.push(shop.shop_id);
      failures.push({ shopId: shop.shop_id, error: shop.error ?? null });
      continue;
    }
    hasData = true;
    for (const { key } of PRODUCT_COUNT_ITEMS) totals[key] += shop.counts[key] ?? 0;
    if (shop.fetched_at && (fetchedAt === null || new Date(shop.fetched_at) < new Date(fetchedAt))) {
      fetchedAt = shop.fetched_at;
    }
  }
  return { totals, failedShopIds, failures, hasData, fetchedAt };
}

/** 跨店合并分组（同 ID 只保留一个名称）。 */
export function mergeGroups(resp: ProductGroupsResponse): GroupItem[] {
  const seen = new Map<string, GroupItem>();
  for (const shop of resp.shops) {
    for (const group of shop.items ?? []) {
      if (!seen.has(group.group_id)) seen.set(group.group_id, group);
    }
  }
  return [...seen.values()];
}

export function priceRange(row: ProductRow): string {
  // 平台的 price_lower / price_higher 理论上有序，仍按数值归一，避免脏数据显示成倒挂区间
  const prices = [row.price_lower_cents, row.price_higher_cents].filter(
    (value): value is number => value !== null,
  );
  if (prices.length === 0) return "暂无";
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  return low === high ? formatCents(low) : `${formatCents(low)} – ${formatCents(high)}`;
}

export function productStateLabel(row: ProductRow): string {
  return row.tab ?? row.status ?? "—";
}

export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PAGE_SIZE));
}

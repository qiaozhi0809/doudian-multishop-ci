import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";
import { EMPTY_TEXT } from "@/lib/empty-text";

export type ProductRow = components["schemas"]["ProductRow"];
export type ProductCountsResponse = components["schemas"]["ProductCountsResponse"];
export type ProductGroupsResponse = components["schemas"]["ProductGroupsResponse"];
export type GroupItem = components["schemas"]["GroupItem"];

export const PAGE_SIZE = 50;
/** 可排序的列，与后端 /api/catalog/products 的 sort 白名单一致；默认按销量倒序（快照里没有商品创建 / 更新时间）。 */
export const PRODUCT_SORT_KEYS = ["shop_name", "tab", "price", "stock_num", "sell_num", "sell_num_30d"] as const;
/** 商品状态：顺序即计数卡顺序与「状态」列的排序顺序；键名也是列表快捷筛选值（quick），与后端 domain/product_status.py 一致。 */
export const PRODUCT_COUNT_ITEMS = [
  { key: "onsale", label: "在售", tone: "success", tabs: ["onsale", "售卖中", "在售"] },
  { key: "draft", label: "草稿", tone: "neutral", tabs: ["draft", "草稿", "草稿箱"] },
  { key: "audit", label: "审核中", tone: "info", tabs: ["audit", "审核中", "待审核"] },
  { key: "sell_out_new", label: "售罄", tone: "warning", tabs: ["sell_out_new", "sell_out", "soldout", "已售罄", "售罄"] },
  { key: "unpass", label: "未通过", tone: "danger", tabs: ["unpass", "unpass_new", "审核未通过", "审核驳回", "未通过"] },
  { key: "forbidden", label: "禁售 / 下架", tone: "danger", tabs: ["forbidden", "已下架", "下架", "禁售", "封禁中", "已封禁"] },
] as const;
export const PRODUCT_QUICK_KEYS = PRODUCT_COUNT_ITEMS.map((item) => item.key);
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
  if (prices.length === 0) return EMPTY_TEXT;
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  return low === high ? formatCents(low) : `${formatCents(low)} 至 ${formatCents(high)}`;
}

/**
 * 状态文案：平台条目的 tab 有中文文案（「售卖中」「已下架」，原样显示，比计数卡的口径更具体），
 * 也有英文代码（样本里的 onSale，大小写不统一），代码换成计数卡的名称。
 */
export function productStateLabel(row: ProductRow): string {
  if (!row.tab) return EMPTY_TEXT;
  if (!/^[A-Za-z_]+$/.test(row.tab)) return row.tab;
  const tab = row.tab.toLowerCase();
  const item = PRODUCT_COUNT_ITEMS.find((entry) => (entry.tabs as readonly string[]).includes(tab));
  return item?.label ?? row.tab;
}

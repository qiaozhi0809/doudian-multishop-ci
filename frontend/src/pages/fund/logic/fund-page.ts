import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";
import { EMPTY_TEXT } from "@/lib/empty-text";

export type FundSummary = components["schemas"]["FundSummary"];
export type ShopFundSummary = components["schemas"]["ShopFundSummary"];
export type UnsettledRow = components["schemas"]["UnsettledRow"];
export type MarginRow = components["schemas"]["MarginRow"];
export type BillItem = components["schemas"]["BillItem"];
export type BillsResponse = components["schemas"]["BillsResponse"];
export type ShopBills = components["schemas"]["ShopBills"];

export const UNSETTLED_PAGE_SIZE = 50;
/** 待结算可排序的列，与后端 /api/fund/unsettled 的 sort 白名单一致；默认最近同步进来的在前。 */
export const UNSETTLED_SORT_KEYS = [
  "shop_name", "income_amount_cents", "platform_service_fee_cents",
  "unsettled_amount_cents", "ecom_order_status", "synced_at",
] as const;
export const FUND_TABS = [
  { value: "unsettled", label: "待结算" },
  { value: "margin", label: "保证金" },
  { value: "bills", label: "账单" },
] as const;
export type FundTab = (typeof FUND_TABS)[number]["value"];

export function isFundTab(value: string | null): value is FundTab {
  return value === "unsettled" || value === "margin" || value === "bills";
}

export const BILL_DAY_OPTIONS = [
  { value: "7", label: "近 7 天" },
  { value: "30", label: "近 30 天" },
] as const;

export function parseBillDays(raw: string | null): number {
  return raw === "7" ? 7 : 30;
}

/** 账单金额字段未校准（附录 F.4）：pending 时界面显示「待探明」，不用猜测值冒充金额。 */
export function billAmountText(item: BillItem): string {
  return item.amount_status === "pending" ? "待探明" : formatCents(item.amount_cents);
}

/** 账单行摘要：优先平台文案，没有就退回单号 / 备注。 */
export function billSummary(item: BillItem): string {
  const raw = item.raw ?? {};
  for (const key of ["bill_type_text", "bill_desc", "remark", "bill_no"]) {
    const value = raw[key];
    if (typeof value === "string" && value) return value;
  }
  return EMPTY_TEXT;
}

export function hasPendingAmount(shops: ShopBills[]): boolean {
  return shops.some((shop) => (shop.items ?? []).some((item) => item.amount_status === "pending"));
}

export const MARGIN_LEVELS: Record<string, string> = {
  low: "低",
  middle: "中",
  high: "高",
};

/** 「等级」列按显示顺序排：低 → 中 → 高，未知等级在后，空值最后。 */
export function marginLevelRank(level: string | null): number | null {
  if (!level) return null;
  const index = Object.keys(MARGIN_LEVELS).indexOf(level);
  return index === -1 ? Object.keys(MARGIN_LEVELS).length : index;
}

export function marginLevelText(level: string | null): string {
  if (!level) return EMPTY_TEXT;
  return MARGIN_LEVELS[level] ?? level;
}

export function settlementDelayText(days: number | null | undefined): string {
  return days === null || days === undefined ? "结算周期待探明" : `确认收货 / 核销后 ${days} 天结算`;
}

export function settledMarginTotal(summary: FundSummary): number {
  return summary.shops.reduce((sum, shop) => sum + (shop.margin_balance_cents ?? 0), 0);
}

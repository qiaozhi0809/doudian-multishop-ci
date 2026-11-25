import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";

export type FundSummary = components["schemas"]["FundSummary"];
export type ShopFundSummary = components["schemas"]["ShopFundSummary"];
export type UnsettledRow = components["schemas"]["UnsettledRow"];
export type MarginRow = components["schemas"]["MarginRow"];
export type BillItem = components["schemas"]["BillItem"];
export type BillsResponse = components["schemas"]["BillsResponse"];
export type ShopBills = components["schemas"]["ShopBills"];

export const UNSETTLED_PAGE_SIZE = 50;
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
  return "—";
}

export function hasPendingAmount(shops: ShopBills[]): boolean {
  return shops.some((shop) => (shop.items ?? []).some((item) => item.amount_status === "pending"));
}

export const MARGIN_LEVELS: Record<string, string> = {
  low: "低",
  middle: "中",
  high: "高",
};

export function marginLevelText(level: string | null): string {
  if (!level) return "暂无";
  return MARGIN_LEVELS[level] ?? level;
}

export function settlementDelayText(days: number | null | undefined): string {
  return days === null || days === undefined ? "结算周期待探明" : `确认收货 / 核销后 ${days} 天结算`;
}

export function settledMarginTotal(summary: FundSummary): number {
  return summary.shops.reduce((sum, shop) => sum + (shop.margin_balance_cents ?? 0), 0);
}

export function unsettledPageCount(total: number): number {
  return Math.max(1, Math.ceil(total / UNSETTLED_PAGE_SIZE));
}

import type { components } from "@/lib/api-types";

export type AftersaleRow = components["schemas"]["AftersaleRow"];
export type AftersaleStatusOption = components["schemas"]["AftersaleStatusOption"];
export type AftersaleCountsResponse = components["schemas"]["AftersaleCountsResponse"];

export const PAGE_SIZE = 50;
export const VIEW_OPTIONS = [
  { value: "todo", label: "待办队列" },
  { value: "all", label: "全部售后" },
] as const;
export type View = (typeof VIEW_OPTIONS)[number]["value"];

export function isView(value: string | null): value is View {
  return value === "todo" || value === "all";
}

/** 状态筛选值是平台数字枚举；取值未公开，选项文案由后端从平台报文里带出。 */
export function parseStatus(raw: string | null): number | undefined {
  if (!raw) return undefined;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : undefined;
}

export interface AggregatedAftersaleCounts {
  pendingTotal: number;
  auditTotal: number;
  approachingDeadline: number;
  failedShopIds: number[];
  failures: { shopId: number; error: string | null }[];
  hasData: boolean;
  fetchedAt: string | null;
}

/** 只合计 `source === "upstream"` 的店；取不到的店单独列出，不当 0 静默合计。 */
export function aggregateAftersaleCounts(resp: AftersaleCountsResponse): AggregatedAftersaleCounts {
  const result: AggregatedAftersaleCounts = {
    pendingTotal: 0,
    auditTotal: 0,
    approachingDeadline: 0,
    failedShopIds: [],
    failures: [],
    hasData: false,
    fetchedAt: null,
  };
  for (const shop of resp.shops) {
    if (shop.source !== "upstream" || !shop.counts) {
      result.failures.push({ shopId: shop.shop_id, error: shop.error ?? null });
      result.failedShopIds.push(shop.shop_id);
      continue;
    }
    result.hasData = true;
    result.pendingTotal += shop.pending_total;
    result.auditTotal += shop.counts.all_audit ?? 0;
    result.approachingDeadline += shop.counts.approaching_deadline_audit ?? 0;
    if (shop.fetched_at && (result.fetchedAt === null || new Date(shop.fetched_at) < new Date(result.fetchedAt))) {
      result.fetchedAt = shop.fetched_at;
    }
  }
  return result;
}

export type DeadlineTone = "neutral" | "warning" | "danger";

/** 平台在售后单未完结时下发处理截止时间；已完结为 NULL（后端已把 0 转成 NULL）。 */
export function deadlineInfo(deadline: string | null, now: number = Date.now()): { text: string; tone: DeadlineTone } {
  if (!deadline) return { text: "已完结", tone: "neutral" };
  const ms = new Date(deadline).getTime() - now;
  if (Number.isNaN(ms)) return { text: "截止时间未知", tone: "neutral" };
  if (ms <= 0) return { text: "已超时", tone: "danger" };
  const hours = Math.ceil(ms / 3_600_000);
  if (hours <= 24) return { text: `剩 ${hours} 小时`, tone: "danger" };
  if (hours <= 72) return { text: `剩 ${Math.ceil(ms / 86_400_000)} 天`, tone: "warning" };
  return { text: `剩 ${Math.ceil(ms / 86_400_000)} 天`, tone: "neutral" };
}

export function statusLabel(row: AftersaleRow): string {
  return row.display.status_text ?? (row.status === null ? "状态未知" : `状态 ${row.status}`);
}

export function typeLabel(row: AftersaleRow): string {
  return row.display.type_text ?? (row.type === null ? "—" : `类型 ${row.type}`);
}

export function pageCount(total: number): number {
  return Math.max(1, Math.ceil(total / PAGE_SIZE));
}

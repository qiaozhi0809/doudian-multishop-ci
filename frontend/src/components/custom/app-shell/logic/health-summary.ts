import type { ShopRow } from "@/lib/use-shops";

export interface HealthSummary {
  /** empty：还没有店铺；error：有店铺停摆需处理；warn：有店铺即将到期 */
  level: "empty" | "ok" | "warn" | "error";
  /** 需处理的店铺数（会话失效、风控暂停、出口异常） */
  errorCount: number;
  /** 即将到期的店铺数（会话、代理） */
  warnCount: number;
}

export interface AttentionRow {
  id: number;
  name: string;
  label: string;
  tone: "danger" | "warning";
  severity: "error" | "warn";
}

const DAY_MS = 86_400_000;
const PROXY_WARN_DAYS = 7;

const daysLeft = (iso: string, now: Date) => Math.ceil((new Date(iso).getTime() - now.getTime()) / DAY_MS);

/**
 * 一家店当前最严重的问题（没有问题为 null）。
 * 顺序：需重新登录 > 风控暂停 > 出口不通 > 出口 IP 重复 > 出口 IP 已变化 > 会话即将过期 > 代理即将到期。
 * 文案与色调按 ui-guidelines 第 5 节；已停用的店铺没有问题。
 */
function worstIssue(shop: ShopRow, now: Date): Omit<AttentionRow, "id" | "name"> | null {
  if (shop.status === "disabled") return null;
  const error = (label: string, tone: AttentionRow["tone"] = "danger") => ({ label, tone, severity: "error" as const });
  const warn = (label: string) => ({ label, tone: "warning" as const, severity: "warn" as const });

  if (shop.status === "needs_login") return error("需重新登录");
  if (shop.paused_reason) return error("风控暂停");
  if (shop.egress_status === "unreachable") return error("出口不通");
  if (shop.egress_status === "duplicate") return error("出口 IP 与其他店重复");
  if (shop.egress_status === "changed") {
    const ip = shop.egress_ip_pending;
    return error(ip ? `出口 IP 已变为 ${ip}，需确认` : "出口 IP 已变化，需确认", "warning");
  }
  if (shop.health === "expiring") {
    if (!shop.expires_at) return warn("即将过期");
    const days = daysLeft(shop.expires_at, now);
    return warn(days > 0 ? `即将过期（剩 ${days} 天）` : "已过期");
  }
  if (shop.proxy_expires_at) {
    const days = daysLeft(shop.proxy_expires_at, now);
    if (days <= 0) return warn("代理已到期");
    if (days <= PROXY_WARN_DAYS) return warn(`代理 ${days} 天后到期`);
  }
  return null;
}

/** 店铺状态汇总：一家店只计一次，按其最严重的问题归类。 */
export function summarizeHealth(shops: ShopRow[], now: Date = new Date()): HealthSummary {
  if (shops.length === 0) return { level: "empty", errorCount: 0, warnCount: 0 };
  const issues = shops.map((s) => worstIssue(s, now));
  const errorCount = issues.filter((i) => i?.severity === "error").length;
  const warnCount = issues.filter((i) => i?.severity === "warn").length;
  return { level: errorCount > 0 ? "error" : warnCount > 0 ? "warn" : "ok", errorCount, warnCount };
}

/** 需要处理的店铺（最严重的问题一行），需处理在前、即将到期在后。 */
export function listAttention(shops: ShopRow[], now: Date = new Date()): AttentionRow[] {
  const rows: AttentionRow[] = [];
  for (const shop of shops) {
    const issue = worstIssue(shop, now);
    if (issue) rows.push({ id: shop.id, name: shop.name, ...issue });
  }
  return rows.sort((a, b) => Number(b.severity === "error") - Number(a.severity === "error"));
}

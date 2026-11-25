import { daysUntil } from "@/lib/time-format";
import type { ShopRow } from "@/lib/use-shops";

export type Tone = "success" | "warning" | "danger" | "neutral";
export interface Badge {
  label: string;
  tone: Tone;
}

const PROXY_WARN_DAYS = 7;

/** 会话状态（ui-guidelines 第 5 节）。 */
export function shopStatusBadge(row: ShopRow, now: Date = new Date()): Badge {
  if (row.status === "disabled") return { label: "已停用", tone: "neutral" };
  if (row.status === "needs_login" || row.health === "expired") return { label: "需重新登录", tone: "danger" };
  if (row.health === "expiring") {
    if (!row.expires_at) return { label: "即将过期", tone: "warning" };
    const days = daysUntil(row.expires_at, now);
    return days > 0 ? { label: `即将过期（剩 ${days} 天）`, tone: "warning" } : { label: "需重新登录", tone: "danger" };
  }
  return { label: "正常", tone: "success" };
}

const EGRESS_BASE: Record<ShopRow["egress_status"], (row: ShopRow) => Badge> = {
  unchecked: () => ({ label: "未检查", tone: "neutral" }),
  ok: (row) => ({ label: `出口正常 · ${row.egress_ip ?? "暂无"}`, tone: "success" }),
  unreachable: () => ({ label: "出口不通", tone: "danger" }),
  changed: (row) => ({
    label: row.egress_ip_pending ? `出口 IP 已变为 ${row.egress_ip_pending}，需确认` : "出口 IP 已变化，需确认",
    tone: "warning",
  }),
  duplicate: () => ({ label: "出口 IP 与其他店重复", tone: "danger" }),
};

/** 出口状态；代理剩 ≤ 7 天（或已到期）时追加提示，出口正常时据此降为 warning / danger。 */
export function egressBadge(row: ShopRow, now: Date = new Date()): Badge {
  if (row.egress_mode === null) return { label: "未设置出口", tone: "neutral" };
  const base = EGRESS_BASE[row.egress_status](row);
  if (row.egress_mode !== "proxy" || !row.proxy_expires_at) return base;

  const days = daysUntil(row.proxy_expires_at, now);
  if (days > PROXY_WARN_DAYS) return base;
  const note = days > 0 ? `代理 ${days} 天后到期` : "代理已到期";
  const expired = days <= 0;
  const tone: Tone = expired ? "danger" : base.tone === "success" || base.tone === "neutral" ? "warning" : base.tone;
  return { label: `${base.label}，${note}`, tone };
}

/** 风控暂停：界面只显示「风控暂停」，原因码用于悬停。 */
export function pausedBadge(row: ShopRow): { label: string; reason: string } | null {
  return row.paused_reason ? { label: "风控暂停", reason: row.paused_reason } : null;
}

/** 扫码需要出口已配置且检查通过。 */
export function canScan(row: ShopRow): boolean {
  return row.egress_mode !== null && row.egress_status === "ok";
}

const BLOCKED: Record<ShopRow["egress_status"], string | null> = {
  ok: null,
  unchecked: "出口未检查通过，不能扫码",
  unreachable: "出口不通，请检查代理是否到期或更换代理",
  changed: "出口 IP 已变化，请先确认新 IP",
  duplicate: "出口 IP 与其他店重复，请更换出口",
};

/** 扫码按钮禁用时的悬停说明；能扫码时为 null。 */
export function scanBlockedReason(row: ShopRow): string | null {
  if (row.egress_mode === null) return "还没有设置出口，请先设置出口";
  return BLOCKED[row.egress_status];
}

/** 界面上扫码按钮的禁用说明：已停用、风控暂停优先，其次是出口问题。 */
export function scanDisabledReason(row: ShopRow): string | null {
  if (row.status === "disabled") return "店铺已停用，不能扫码";
  if (row.paused_reason) return "风控暂停中，请先恢复";
  return scanBlockedReason(row);
}

/** 取号就绪；未就绪时 detail 为原因（悬停显示）。 */
export function readyBadge(row: ShopRow): Badge & { detail: string | null } {
  if (row.ready_for_label) return { label: "就绪", tone: "success", detail: null };
  return { label: "未就绪", tone: "neutral", detail: row.not_ready_reasons.join("；") || null };
}

export function egressModeLabel(row: ShopRow): string {
  return row.egress_mode === "direct" ? "直连" : row.egress_mode === "proxy" ? "代理" : "未设置";
}

export type PrimaryAction = "set-egress" | "check-egress" | "login";

/**
 * 行内直接显示的主操作（引导的顺序：设置出口 → 检查出口 → 扫码登录）。
 * 扫码前必须先检查出口，所以出口没设置 / 没通过时不显示扫码登录。
 */
export function primaryAction(row: ShopRow): PrimaryAction {
  if (row.egress_mode === null) return "set-egress";
  if (row.egress_status !== "ok") return "check-egress";
  return "login";
}

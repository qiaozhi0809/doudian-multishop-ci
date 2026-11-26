import type { components } from "@/lib/api-types";

type PoolItem = components["schemas"]["PoolItem"];
type PoolCheckOut = components["schemas"]["PoolCheckOut"];

export type PoolTone = "success" | "info" | "danger" | "muted";

/** 池项状态：直接反映绑定关系与到期（过期且被占用最醒目，过期空闲只淡化）。 */
export function poolStatus(item: PoolItem): { label: string; tone: PoolTone } {
  if (item.expiry_state === "expired") {
    return { label: "已过期", tone: item.in_use_by ? "danger" : "muted" };
  }
  if (item.in_use_by) return { label: `已用于「${item.in_use_by.shop_name}」`, tone: "info" };
  return { label: "空闲", tone: "success" };
}

/** 「状态」列的排序值：按显示的文案排 —— 空闲 → 已用于「店名」（按店名）→ 已过期。 */
export function poolStatusSortValue(item: PoolItem): string {
  const rank = item.expiry_state === "expired" ? 2 : item.in_use_by ? 1 : 0;
  return `${rank} ${poolStatus(item).label}`;
}

const REASON_TEXT = {
  timeout: "检查超时（10 秒）",
  proxy_unavailable: "代理连不上，请检查地址、账号密码或是否到期",
  network: "网络错误，请稍后重试",
  bad_echo: "回显地址返回的不是 IP，请检查设置里的回显地址",
} as const;

export function checkReasonText(reason: PoolCheckOut["reason"]): string {
  return reason ? REASON_TEXT[reason] : "";
}

export interface CheckNotice {
  tone: "success" | "warning" | "danger";
  text: string;
}

/** 手动检查的结果提示：通过显示出口 IP 与耗时；IP 已被别的店使用时给出警告。 */
export function checkNotice(display: string, out: PoolCheckOut): CheckNotice {
  if (out.reason || !out.ip) {
    return { tone: "danger", text: `${display}：${checkReasonText(out.reason) || "检查失败"}` };
  }
  const base = `${display}：检查通过，出口 IP ${out.ip}（${out.elapsed_ms} ms）`;
  if (out.ip_in_use_by) {
    return { tone: "warning", text: `${base}，该 IP 已被店铺「${out.ip_in_use_by.shop_name}」使用` };
  }
  return { tone: "success", text: base };
}

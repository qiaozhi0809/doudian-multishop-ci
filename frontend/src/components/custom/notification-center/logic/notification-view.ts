/** 通知的纯视图逻辑：档位色调、面板分组、是否该弹提醒。 */
import type { NoticeEvent } from "@/components/custom/notice/notice-types";
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type NotificationItem = Schemas["NotificationItem"];
export type NotificationPage = Schemas["NotificationPage"];
export type NotificationSummary = Schemas["NotificationSummary"];
export type StrongOpenShop = Schemas["StrongOpenShop"];
export type StrongProblem = Schemas["StrongProblem"];
export type NotificationLevel = NotificationItem["level"];
export type Tone = "danger" | "warning" | "info";

/** SSE `notification` 事件；全部已读时 item 为 null。 */
export interface NotificationEvent {
  action: "created" | "updated" | "resolved" | "read";
  item: NotificationItem | null;
  alert: boolean;
}

const TONES: Record<NotificationLevel, Tone> = { strong: "danger", medium: "warning", weak: "info" };

export const levelTone = (level: NotificationLevel): Tone => TONES[level];

const isOpenState = (item: NotificationItem): boolean => item.state_key !== null && item.resolved_at === null;

/** 面板分组：未解决的状态类固定置顶（open），其余保持原顺序（recent）。 */
export function groupForPanel(items: NotificationItem[]): { open: NotificationItem[]; recent: NotificationItem[] } {
  return { open: items.filter(isOpenState), recent: items.filter((item) => !isOpenState(item)) };
}

/** 提醒去重键：同一条通知合并后数量变多（又来了新单）算新的提醒。 */
export const alertKey = (item: NotificationItem): string => `${item.id}:${item.count}`;

/** 只对 alert=true 且本会话还没提醒过（按 id + 数量）的通知弹提醒。 */
export const shouldAlert = (event: NotificationEvent, alerted: string[]): boolean =>
  event.alert && event.item !== null && !alerted.includes(alertKey(event.item));

/** 横条里的问题名（与后端通知标题一致）。 */
const PROBLEM_LABELS: Partial<Record<NotificationItem["kind"], string>> = {
  login_expired: "登录失效",
  egress_unreachable: "出口不通",
  egress_changed: "出口 IP 已变化",
  egress_duplicate: "出口 IP 与其他店重复",
  risk_paused: "风控暂停",
  ship_deadline: "临近发货超时",
  im_waiting: "超 3 分钟未回复",
};

/** 横条最多逐店列出几家，超过合并为一行。 */
export const BANNER_MAX_ROWS = 3;

export interface BannerProblem {
  kind: NotificationItem["kind"];
  label: string;
  link: string;
}

export interface BannerRow {
  shopId: number;
  shopName: string;
  /** 「店A：登录失效、出口不通」 */
  text: string;
  /** 每个问题各自跳转 */
  problems: BannerProblem[];
}

export type BannerView = { kind: "none" } | { kind: "rows"; rows: BannerRow[] } | { kind: "merged"; text: string };

/**
 * 后端没给链接时兜底：临近超时 → 该店订单（不加快捷筛选，已超时与临近的都在；
 * 后端按是否有超时单给 ship_delay / exp_ship），飞鸽等待超时 → 该店消息页的超时筛选，
 * 其余 → 店铺页高亮该店。
 */
function fallbackLink(kind: NotificationItem["kind"], shopId: number): string {
  if (kind === "ship_deadline") return `/orders?shops=${shopId}`;
  if (kind === "im_waiting") return `/messages?shops=${shopId}&quick=overdue`;
  return `/shops?shop=${shopId}`;
}

/** 未解决的强提醒，一店一行「店A：登录失效、出口不通」，每个问题跳各自的链接（面板「待处理」全部列出）。 */
export function openRows(shops: StrongOpenShop[]): BannerRow[] {
  return shops.map((shop) => {
    const problems = shop.problems.map((p) => ({
      kind: p.kind,
      label: PROBLEM_LABELS[p.kind] ?? "需要处理",
      link: p.link ?? fallbackLink(p.kind, shop.shop_id),
    }));
    return {
      shopId: shop.shop_id,
      shopName: shop.shop_name,
      text: `${shop.shop_name}：${problems.map((p) => p.label).join("、")}`,
      problems,
    };
  });
}

/** 顶部横条：同 openRows；超过 3 家合并为「N 家店需要处理」。 */
export function bannerView(shops: StrongOpenShop[]): BannerView {
  if (shops.length === 0) return { kind: "none" };
  if (shops.length > BANNER_MAX_ROWS) return { kind: "merged", text: `${shops.length} 家店需要处理` };
  return { kind: "rows", rows: openRows(shops) };
}

/** 分页的最后一页（至少为 1）。 */
export const lastPage = (total: number, pageSize: number): number =>
  pageSize > 0 ? Math.max(1, Math.ceil(total / pageSize)) : 1;

/** 中档弹窗停留 5 秒。 */
export const MEDIUM_HOLD_MS = 5000;

/** 有专属图标的事件；其余通知归为 system。 */
const NOTICE_EVENTS: Partial<Record<NotificationItem["kind"], NoticeEvent>> = {
  new_order: "order",
  new_aftersale: "aftersale",
  new_message: "message",
};

export interface AlertNotice {
  text: string;
  body?: string;
  event: NoticeEvent;
  tone: Tone;
  key: string;
  persistent: boolean;
  holdMs?: number;
}

/** 通知在右下角弹窗里的 key（同一条通知只留一个弹窗）。 */
export const noticeKey = (id: number): string => `notification:${id}`;

/** 右下角弹窗：只弹事件类，强档常驻、中档 5 秒、弱档不弹；状态类（有 state_key）由顶部横条显示，不弹。 */
export function alertNotice(item: NotificationItem): AlertNotice | null {
  if (item.level === "weak" || item.state_key !== null) return null;
  const content = {
    text: item.title,
    ...(item.body ? { body: item.body } : {}),
    event: NOTICE_EVENTS[item.kind] ?? "system",
    key: noticeKey(item.id),
  };
  return item.level === "strong"
    ? { ...content, tone: "danger", persistent: true }
    : { ...content, tone: "warning", persistent: false, holdMs: MEDIUM_HOLD_MS };
}

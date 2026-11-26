/** 通知的纯视图逻辑：档位色调、面板分组、是否该弹提醒。 */
import type { components } from "@/lib/api-types";

type Schemas = components["schemas"];
export type NotificationItem = Schemas["NotificationItem"];
export type NotificationPage = Schemas["NotificationPage"];
export type NotificationSummary = Schemas["NotificationSummary"];
export type StrongOpenShop = Schemas["StrongOpenShop"];
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

/** 只对 alert=true 且本会话还没提醒过的通知弹提醒。 */
export const shouldAlert = (event: NotificationEvent, alerted: number[]): boolean =>
  event.alert && event.item !== null && !alerted.includes(event.item.id);

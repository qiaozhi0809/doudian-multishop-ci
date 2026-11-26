import { withShopFilter } from "@/components/custom/app-shell/logic/shop-filter";
import type { components } from "@/lib/api-types";

export type Conversation = components["schemas"]["ImConversation"];
export type ConversationPage = components["schemas"]["ImConversationPage"];
export type Counts = components["schemas"]["ImCounts"];
export type Thread = components["schemas"]["ImThread"];
export type Message = components["schemas"]["ImMessage"];
export type ShopStatus = components["schemas"]["ImShopStatus"];
export type FocusResult = components["schemas"]["ImFocusResult"];

/** 快捷筛选键：与后端 ImQuick、计数接口字段一致。 */
export const IM_QUICK = ["unread", "waiting", "overdue", "today"] as const;
export type ImQuick = (typeof IM_QUICK)[number];

/** 与后端 ImConversationSort 白名单一致；不带 sort 时按等待时间倒序。 */
export const IM_SORT_KEYS = ["waiting", "last_at", "unread", "shop_name"] as const;
export const PAGE_SIZE = 50;

/** 超过这么久未回复算超时，与后端 WAIT_ALERT 一致。 */
const OVERDUE_SECONDS = 180;

/** 买家到 now 已等待的整秒数（从 waiting_since 起算，同后端）；没在等返回 null。 */
export function waitSecondsAt(waitingSince: string | null, now: Date): number | null {
  if (!waitingSince) return null;
  const since = Date.parse(waitingSince);
  if (Number.isNaN(since)) return null;
  return Math.max(0, Math.floor((now.getTime() - since) / 1000));
}

export function formatWait(seconds: number | null): string {
  if (seconds === null) return "";
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分 ${seconds % 60} 秒`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
}

export const isOverdue = (seconds: number | null): boolean => seconds !== null && seconds > OVERDUE_SECONDS;

const SENDER_LABELS = { buyer: "买家", agent: "客服", robot: "智能客服", platform: "平台" } as const;

export const senderLabel = (role: Message["sender_role"]) => SENDER_LABELS[role];

/** 订单接口没有买家筛选，只带店铺。 */
export const ordersLink = (shopId: number): string => withShopFilter("/orders", [shopId]);

export interface Selection {
  shopId: number;
  conversationId: string;
}

export const selectionKey = (shopId: number, conversationId: string): string => `${shopId}:${conversationId}`;

const SELECTION_PARAM = "conv";
/** 店铺编号 + 会话编号（字符范围同后端 ConversationId，可含冒号）。 */
const SELECTION_PATTERN = /^([1-9]\d*):([A-Za-z0-9_:.-]{1,128})$/;

/** 当前选中的会话放在 URL：`conv=<shop_id>:<conversation_id>`。 */
export const selectionParam = {
  read(params: URLSearchParams): Selection | null {
    const match = SELECTION_PATTERN.exec(params.get(SELECTION_PARAM) ?? "");
    // 「.」「..」会被浏览器当成路径段，请求会打到别的地址
    if (!match || match[2] === "." || match[2] === "..") return null;
    return { shopId: Number(match[1]), conversationId: match[2] };
  },
  write(prev: URLSearchParams, selection: Selection | null): URLSearchParams {
    const next = new URLSearchParams(prev);
    if (selection) next.set(SELECTION_PARAM, selectionKey(selection.shopId, selection.conversationId));
    else next.delete(SELECTION_PARAM);
    return next;
  },
};

/** 选中会话在当前这一页列表里的行。 */
export const selectedRow = (items: Conversation[] | undefined, selection: Selection | null): Conversation | undefined =>
  selection
    ? items?.find((c) => c.shop_id === selection.shopId && c.conversation_id === selection.conversationId)
    : undefined;

/** 选中的店不在当前店铺筛选里时视为未选中（空筛选 = 全部店铺）。 */
export const inShopScope = (shopId: number, shopIds: number[]): boolean =>
  shopIds.length === 0 || shopIds.includes(shopId);

const RESTARTABLE: ReadonlySet<ShopStatus["state"]> = new Set(["needs_refresh", "backoff", "stopped"]);

export const canRestart = (state: ShopStatus["state"]): boolean => RESTARTABLE.has(state);

/** 状态条要列的店：当前店铺范围内、不在接收中的。 */
export const stoppedShops = (statuses: ShopStatus[], shopIds: number[]): ShopStatus[] =>
  statuses.filter((s) => s.state !== "running" && inShopScope(s.shop_id, shopIds));

/** 会话是实时变化的：当前页超出末页时回到末页。 */
export const clampPage = (page: number, total: number, pageSize: number): number =>
  Math.min(page, Math.max(1, Math.ceil(total / pageSize)));

import type { components } from "@/lib/api-types";

type Conversation = components["schemas"]["ImConversation"];
type Message = components["schemas"]["ImMessage"];
type ShopStatus = components["schemas"]["ImShopStatus"];

/** 秒数之前的时刻（UTC ISO）。 */
export const secondsAgo = (seconds: number) => new Date(Date.now() - seconds * 1000).toISOString();

export function makeConversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    shop_id: 1,
    shop_name: "测试小铺",
    conversation_id: "conv-test-1",
    buyer: "测试买家",
    preview: "在吗",
    unread: 2,
    last_at: secondsAgo(200),
    waiting_since: secondsAgo(200),
    wait_seconds: 200,
    ...overrides,
  };
}

export function makeMessage(overrides: Partial<Message> = {}): Message {
  return { message_id: "m1", sender_role: "buyer", text: "在吗", sent_at: secondsAgo(200), ...overrides };
}

export function makeImStatus(overrides: Partial<ShopStatus> = {}): ShopStatus {
  return {
    shop_id: 1,
    shop_name: "测试小铺",
    state: "running",
    state_label: "接收中",
    since: secondsAgo(600),
    next_retry_at: null,
    last_error: null,
    ...overrides,
  };
}

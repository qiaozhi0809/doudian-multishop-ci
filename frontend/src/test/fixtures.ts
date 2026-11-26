import type { components } from "@/lib/api-types";

export type ShopRow = components["schemas"]["ShopRow"];

export function makeShop(overrides: Partial<ShopRow> = {}): ShopRow {
  return {
    id: 1,
    name: "店铺甲",
    entity: null,
    shop_no: null,
    status: "active",
    health: "healthy",
    expires_at: null,
    paused_reason: null,
    egress_mode: "proxy",
    proxy_display: "1.2.3.4:8000",
    egress_ip: "1.2.3.4",
    egress_ip_pending: null,
    egress_status: "ok",
    proxy_expires_at: null,
    ready_for_label: true,
    not_ready_reasons: [],
    admin_name: null,
    shop_name: null,
    platform_shop_id: null,
    bank_name: null,
    bank_tail: null,
    im_enabled: false,
    ...overrides,
  };
}

type StrongKind = components["schemas"]["StrongOpenShop"]["kinds"][number];

/** 通知摘要：这些店有未解决的强提醒（顶部横条里列出的店）。 */
export function strongOpenSummary(shops: { shopId: number; kinds: StrongKind[] }[]) {
  return {
    unread: shops.length,
    strong_open: shops.map(({ shopId, kinds }) => ({
      shop_id: shopId,
      shop_name: `店铺 ${shopId}`,
      kinds,
      link: null,
      problems: kinds.map((kind) => ({ kind, link: null })),
    })),
  };
}

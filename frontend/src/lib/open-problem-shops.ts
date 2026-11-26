import type { components } from "./api-types";

type StrongOpenShop = components["schemas"]["StrongOpenShop"];
type Kind = StrongOpenShop["kinds"][number];

/** 让店铺取不到平台数据、且已在顶部横条列出的问题：登录、出口、风控。 */
const FETCH_BLOCKING: ReadonlySet<Kind> = new Set<Kind>([
  "login_expired",
  "egress_unreachable",
  "egress_changed",
  "egress_duplicate",
  "risk_paused",
]);

/** 横条里有登录 / 出口 / 风控问题的店。 */
export function shopsWithOpenProblems(strongOpen: StrongOpenShop[]): Set<number> {
  return new Set(strongOpen.filter((shop) => shop.kinds.some((kind) => FETCH_BLOCKING.has(kind))).map((shop) => shop.shop_id));
}

/** 页面「N 家店未取到」只列横条里没有的店，同一个问题不重复提示。 */
export function withoutShops<T extends { shopId: number }>(failures: T[], shopIds: ReadonlySet<number>): T[] {
  return failures.filter((failure) => !shopIds.has(failure.shopId));
}

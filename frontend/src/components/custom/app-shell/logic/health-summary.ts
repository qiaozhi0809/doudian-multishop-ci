import type { ShopRow } from "@/lib/use-shops";

export interface HealthSummary {
  level: "ok" | "warn" | "error";
  needsLogin: number;
  expiring: number;
}

export interface AttentionRow {
  id: number;
  name: string;
  kind: "needs_login" | "expiring";
}

const kindOf = (shop: ShopRow): AttentionRow["kind"] | null => {
  if (shop.status === "needs_login") return "needs_login";
  if (shop.status === "active" && shop.health === "expiring") return "expiring";
  return null;
};

/** 会话健康汇总：有 needs_login 为 error，否则有 expiring 为 warn；已停用的店铺不计入。 */
export function summarizeHealth(shops: ShopRow[]): HealthSummary {
  const kinds = shops.map(kindOf);
  const needsLogin = kinds.filter((k) => k === "needs_login").length;
  const expiring = kinds.filter((k) => k === "expiring").length;
  const level = needsLogin > 0 ? "error" : expiring > 0 ? "warn" : "ok";
  return { level, needsLogin, expiring };
}

/** 需要处理的店铺：需重新登录排在即将过期之前。 */
export function listAttention(shops: ShopRow[]): AttentionRow[] {
  const rows: AttentionRow[] = [];
  for (const shop of shops) {
    const kind = kindOf(shop);
    if (kind) rows.push({ id: shop.id, name: shop.name, kind });
  }
  return rows.sort((a, b) => Number(b.kind === "needs_login") - Number(a.kind === "needs_login"));
}

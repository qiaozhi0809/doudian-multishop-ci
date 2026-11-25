import type { components } from "@/lib/api-types";

type PoolItem = components["schemas"]["PoolItem"];

/** 可分配给店铺的池项：没有被启用店铺占用，且未过期。 */
export function availablePoolItems(items: PoolItem[]): PoolItem[] {
  return items.filter((i) => i.in_use_by === null && i.expiry_state !== "expired");
}

/** 选项文案：`主机:端口 · 到期 MM-DD`；没有到期日显示「不限期」。 */
export function poolOptionLabel(item: PoolItem): string {
  const expiry = item.expires_at ? `到期 ${item.expires_at.slice(5, 10)}` : "不限期";
  return `${item.proxy_display} · ${expiry}`;
}

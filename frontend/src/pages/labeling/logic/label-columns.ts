import type { components } from "@/lib/api-types";
import { isLocalStatus, localStatusBadge } from "@/lib/order-status";

export type LabelOrder = components["schemas"]["LabelOrderRow"];
export type LabelItem = LabelOrder["items"][number];
export type Stage = "pending" | "labeled";

/** 后端状态串 → 徽章；未知值不猜测，原样显示为中性。 */
export function rowStatusBadge(status: string) {
  return isLocalStatus(status)
    ? localStatusBadge(status)
    : { label: status, tone: "neutral" as const };
}

export const PAGE_SIZE = 50;

export const STAGE_OPTIONS: { value: Stage; label: string }[] = [
  { value: "pending", label: "待打单" },
  { value: "labeled", label: "待发货" },
];

export const isStage = (value: string | null): value is Stage =>
  value === "pending" || value === "labeled";

/** 有阻断原因的订单不可勾选（缺 combine_id / sku_id、已有面单等，gaps API-04）。 */
export const canSelect = (row: LabelOrder): boolean => row.blocked_reason === null;

export const pageCount = (total: number) => Math.max(1, Math.ceil(total / PAGE_SIZE));

/** 商品摘要：首个商品名 + 「等 N 件」（N 为商品行数）。 */
export function itemSummary(items: LabelItem[]): string {
  if (items.length === 0) return "暂无";
  const first = items[0].product_name || "暂无";
  return items.length > 1 ? `${first} 等 ${items.length} 件` : first;
}

/** 列表刷新后保留仍存在且仍可选中的勾选（SSE 刷新不丢选择）。 */
export function pruneSelection(
  selected: ReadonlySet<number>,
  rows: LabelOrder[],
): Set<number> {
  const selectable = new Set(rows.filter(canSelect).map((row) => row.id));
  return new Set([...selected].filter((id) => selectable.has(id)));
}

export function allSelected(selected: ReadonlySet<number>, rows: LabelOrder[]): boolean {
  const selectable = rows.filter(canSelect);
  return selectable.length > 0 && selectable.every((row) => selected.has(row.id));
}

export function toggleAll(selected: ReadonlySet<number>, rows: LabelOrder[]): Set<number> {
  const selectable = rows.filter(canSelect);
  if (allSelected(selected, rows)) {
    const ids = new Set(selectable.map((row) => row.id));
    return new Set([...selected].filter((id) => !ids.has(id)));
  }
  return new Set([...selected, ...selectable.map((row) => row.id)]);
}

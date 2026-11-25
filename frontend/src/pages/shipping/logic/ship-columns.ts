import type { components } from "@/lib/api-types";

export type ShipOrder = components["schemas"]["ShipPoolRow"];

export const PAGE_SIZE = 50;

/** 服务端只返回可发货的订单；面单号缺失时仍不可勾选。 */
export function canSelect(row: ShipOrder): boolean {
  return (
    Boolean(row.tracking_no) &&
    (row.status === "label_obtained" || row.status === "printed")
  );
}

const selectableIds = (rows: readonly ShipOrder[]): number[] =>
  rows.filter(canSelect).map((row) => row.id);

/** 只保留仍然存在且可选中的勾选（SSE 刷新后失效行自动移除）。 */
export function pruneSelection(
  selected: ReadonlySet<number>,
  rows: readonly ShipOrder[],
): Set<number> {
  const ids = new Set(selectableIds(rows));
  return new Set([...selected].filter((id) => ids.has(id)));
}

export function toggleAll(
  selected: ReadonlySet<number>,
  rows: readonly ShipOrder[],
): Set<number> {
  const ids = selectableIds(rows);
  if (ids.length > 0 && ids.every((id) => selected.has(id))) return new Set();
  return new Set(ids);
}

export function allSelected(
  selected: ReadonlySet<number>,
  rows: readonly ShipOrder[],
): boolean {
  const ids = selectableIds(rows);
  return ids.length > 0 && ids.every((id) => selected.has(id));
}

/** 同一 (店, 快递, 运单号) 是一个包裹：用于提交前展示与二次确认文案。 */
export function selectedPackages(
  selected: ReadonlySet<number>,
  rows: readonly ShipOrder[],
): number {
  const keys = new Set<string>();
  for (const row of rows) {
    if (selected.has(row.id)) {
      keys.add(`${row.shop_id}:${row.courier_code}:${row.tracking_no}`);
    }
  }
  return keys.size;
}

export function selectedRows(
  selected: ReadonlySet<number>,
  rows: readonly ShipOrder[],
): ShipOrder[] {
  return rows.filter((row) => selected.has(row.id));
}

export const pageCount = (total: number): number =>
  Math.max(1, Math.ceil(total / PAGE_SIZE));

export function rowStatusLabel(row: ShipOrder): string {
  if (row.status === "printed") return "已打印";
  return "已取号";
}

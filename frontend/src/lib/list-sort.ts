/**
 * 列表排序（全站一致）：
 * - 分页列表在服务端排序：URL 里放 `sort=<字段>&order=asc|desc`，原样发给后端白名单参数，改排序回到第 1 页；
 * - 一次全量返回的表在前端排序（sortRows）；
 * - 没有 sort 时用列表自己的默认排序，表头不显示排序状态（默认排序列不带常驻底色）。
 */

export type SortDirection = "asc" | "desc";
export interface ListSort {
  key: string;
  direction: SortDirection;
}

/** 从 URL 读排序；字段不在白名单里视为没有排序（避免把手改的 URL 发给后端得到 422）。 */
export function readSort(params: URLSearchParams, allowed: readonly string[]): ListSort | null {
  const key = params.get("sort");
  if (!key || !allowed.includes(key)) return null;
  return { key, direction: params.get("order") === "desc" ? "desc" : "asc" };
}

/** 写排序到 URL，并回到第 1 页。 */
export function writeSort(prev: URLSearchParams, sort: ListSort | null): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (sort) {
    next.set("sort", sort.key);
    next.set("order", sort.direction);
  } else {
    next.delete("sort");
    next.delete("order");
  }
  next.delete("page");
  return next;
}

/** 发给后端的查询参数；没有排序时不带，后端用默认排序。 */
export function sortQuery(sort: ListSort | null): { sort?: string; order?: SortDirection } {
  return sort ? { sort: sort.key, order: sort.direction } : {};
}

/** 序号从哪里开始数：第 2 页（每页 50）从 51 开始，即偏移 50。 */
export const seqOffset = (page: number, pageSize: number): number => Math.max(0, page - 1) * pageSize;

const collator = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });
const isEmpty = (value: unknown) => value === null || value === undefined || value === "";

/** 前端排序：数字按大小、文本按中文排序规则；空值不论升降都在最后（与后端一致），相等时保持原顺序。 */
export function sortRows<T>(rows: readonly T[], sort: ListSort | null, value: (row: T, key: string) => unknown): T[] {
  if (!sort) return [...rows];
  return rows
    .map((row, index) => ({ row, index, v: value(row, sort.key) }))
    .sort((a, b) => {
      if (isEmpty(a.v) || isEmpty(b.v)) return isEmpty(a.v) === isEmpty(b.v) ? a.index - b.index : isEmpty(a.v) ? 1 : -1;
      const result =
        typeof a.v === "number" && typeof b.v === "number" ? a.v - b.v : collator.compare(String(a.v), String(b.v));
      return (sort.direction === "asc" ? result : -result) || a.index - b.index;
    })
    .map((entry) => entry.row);
}

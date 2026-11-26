import { ArrowUp } from "lucide-react";
import type { ListSort } from "@/lib/list-sort";
import styles from "./sort-header.module.css";

interface SortHeaderProps {
  label: string;
  sortKey: string;
  sort: ListSort | null;
  onSort: (sort: ListSort) => void;
  numeric?: boolean;
  className?: string;
}

/**
 * 手写表格（打单发货：勾选列有禁用行，Arc 表格不支持）的可排序表头，交互与 Arc SortableDataTable 一致：
 * 点一次升序、再点降序，排序中的列显示箭头；悬停时浅色箭头提示可排序。
 */
export function SortHeader({ label, sortKey, sort, onSort, numeric = false, className }: SortHeaderProps) {
  const active = sort?.key === sortKey;
  const descending = active && sort.direction === "desc";
  const next: ListSort = { key: sortKey, direction: active && sort.direction === "asc" ? "desc" : "asc" };
  return (
    <th
      scope="col"
      className={className}
      aria-sort={active ? (descending ? "descending" : "ascending") : "none"}
      data-numeric={numeric || undefined}
    >
      <button
        type="button"
        className={styles.button}
        data-numeric={numeric || undefined}
        data-active={active || undefined}
        onClick={() => onSort(next)}
      >
        <span>{label}</span>
        <ArrowUp className={styles.arrow} data-desc={descending || undefined} size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
    </th>
  );
}

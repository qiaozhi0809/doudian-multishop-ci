import type { CSSProperties } from "react";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";

/**
 * 表格列宽：页面按内容写像素宽，这里换成百分比，让表格默认铺满容器；
 * 像素之和作为「有数据时」的最小表宽，只有容器确实放不下内容才横向滚动。
 * 空表格不加最小宽度（见 styles.css 的 .table-fit），不会出现滚动条。
 */
export function fitColumns<T>(
  columns: DataColumn<T>[],
  fixedKeys: readonly string[] = [],
): { columns: DataColumn<T>[]; minWidth: number } {
  const px = (column: DataColumn<T>) => (typeof column.width === "number" ? column.width : 0);
  const minWidth = columns.reduce((sum, column) => sum + px(column), 0);
  // 固定列（如序号）保留像素宽；浏览器在 table-layout: fixed 下先扣掉像素列，再按百分比分剩下的宽度
  const flexible = columns.reduce((sum, column) => sum + (fixedKeys.includes(column.key) ? 0 : px(column)), 0);
  if (flexible === 0) return { columns, minWidth };
  return {
    minWidth,
    columns: columns.map((column) =>
      typeof column.width === "number" && !fixedKeys.includes(column.key)
        ? { ...column, width: `${Number(((column.width / flexible) * 100).toFixed(3))}%` }
        : column,
    ),
  };
}

/** 包裹表格的容器样式：把最小表宽交给 .table-fit 使用。 */
export const tableFitStyle = (minWidth: number): CSSProperties =>
  ({ "--table-min-width": `${minWidth}px` }) as CSSProperties;

/**
 * 全站统一的列宽（像素，含左右内边距）：19 位单号（订单号 / 售后单号 / 待结算订单号）与「2026-11-25 07:05」
 * 这种完整时间都不换行、不截断；放不下时整表横向滚动，绝不重叠或折成两行。
 */
export const ID_COL_WIDTH = 196;
export const TIME_COL_WIDTH = 148;

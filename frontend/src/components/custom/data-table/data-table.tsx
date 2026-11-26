import { useState, type CSSProperties } from "react";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { EMPTY_TEXT } from "@/lib/empty-text";
import { sortRows, type ListSort } from "@/lib/list-sort";
import { fitColumns } from "@/lib/table-columns";

/** 序号列宽（像素，不随表宽伸缩，放得下 4 位数）；表头与数字都居中；第 2 列（主标识列）固定在它右边，见 styles.css 的 .table-fit[data-seq]。 */
export const SEQ_WIDTH = 56;
const SEQ = "__seq";
const ORIGINAL = "__row";

/** 列定义：Arc 的 DataColumn，另加 sortValue —— 前端排序时按它排（单元格显示的是组合文案时，按显示顺序排而不是原始码）。 */
export type TableColumn<T> = DataColumn<T> & { sortValue?: (row: T) => unknown };

export interface DataTableProps<T extends Record<string, unknown>> {
  rows: T[];
  /** 第一列是主标识列（店铺 / 订单号 / 商品），与序号一起固定在左侧。可排序列写 sortable: true。 */
  columns: TableColumn<T>[];
  rowKey: (row: T) => string;
  caption: string;
  emptyMessage: string;
  /** 受控排序（分页列表：排序在 URL、由服务端完成）；不传时表格自己记排序并在前端排序。null = 默认排序。 */
  sort?: ListSort | null;
  onSortChange?: (sort: ListSort) => void;
  /** rows 已按 sort 排好（服务端排序），不再在前端排序。 */
  serverSorted?: boolean;
  /** 序号从 seqOffset + 1 开始（翻页连续）。 */
  seqOffset?: number;
  /** 页面自己的容器样式（如右侧固定操作列）。 */
  className?: string;
}

const isEmpty = (value: unknown) => value === null || value === undefined || value === "";

/**
 * 全站列表表格：第一列「序号」（窄列、表头与数字居中、翻页连续），序号 + 主标识列固定在左侧，列宽按 fitColumns 铺满。
 *
 * 排序与 Arc SortableDataTable 的表头交互一致（点表头升序，再点降序，带箭头）。行的顺序由这里决定
 * （服务端排好或前端 sortRows），再把当前排序列的值换成名次交给 Arc，Arc 的内部排序只是复现这个顺序，
 * 序号因此与显示顺序一致。没有排序时不给 Arc defaultSort，默认排序列不显示底色。
 */
export function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
  rowKey,
  caption,
  emptyMessage,
  sort: controlled,
  onSortChange,
  serverSorted = false,
  seqOffset = 0,
  className,
}: DataTableProps<T>) {
  const [own, setOwn] = useState<ListSort | null>(null);
  const sort = controlled !== undefined ? controlled : own;
  const original = (row: Record<string, unknown>) => row[ORIGINAL] as T;

  const sortValueOf = (row: T, key: string) => {
    const column = columns.find((c) => c.key === key);
    return column?.sortValue ? column.sortValue(row) : row[key];
  };
  const ordered = serverSorted || !sort ? rows : sortRows(rows, sort, sortValueOf);
  const display = ordered.map((row, index) => ({
    ...row,
    [SEQ]: seqOffset + index + 1,
    ...(sort ? { [sort.key]: sort.direction === "asc" ? index : -index } : {}),
    [ORIGINAL]: row,
  })) as Record<string, unknown>[];

  const wrapped: DataColumn<Record<string, unknown>>[] = [
    { key: SEQ, label: "序号", sortable: false, numeric: false, width: SEQ_WIDTH, render: (value) => String(value) },
    ...columns.map((column) => ({
      ...column,
      sortable: column.sortable === true,
      // 对齐只看列声明：numeric 的列表头与单元格都右对齐（Arc 用同一个 data-numeric 驱动 th 和 td），
      // 其余列表头与单元格都左对齐；不按数据猜（状态码是数字但显示文字，不能右对齐）
      numeric: column.numeric === true,
      render: (_: unknown, row: Record<string, unknown>) => {
        const source = original(row);
        const value = source[column.key];
        return column.render ? column.render(value, source) : isEmpty(value) ? EMPTY_TEXT : String(value);
      },
    })),
  ];
  const fitted = fitColumns(wrapped, [SEQ]);

  return (
    <div
      className={["table-fit", className].filter(Boolean).join(" ")}
      data-seq=""
      style={{ "--table-min-width": `${fitted.minWidth}px`, "--seq-width": `${SEQ_WIDTH}px` } as CSSProperties}
    >
      <SortableDataTable<Record<string, unknown>>
        // 排序变了就重新挂载，让 Arc 的内部排序状态跟上受控排序（URL 变化、回到默认排序）
        key={sort ? `${sort.key}:${sort.direction}` : "default"}
        rows={display}
        columns={fitted.columns}
        rowKey={(row) => rowKey(original(row))}
        caption={caption}
        emptyMessage={emptyMessage}
        defaultSort={sort ?? undefined}
        onSortChange={(next) => {
          const value: ListSort = { key: next.key, direction: next.direction };
          if (controlled === undefined) setOwn(value);
          onSortChange?.(value);
        }}
      />
    </div>
  );
}

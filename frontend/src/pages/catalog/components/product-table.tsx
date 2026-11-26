import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "@/components/custom/data-table/data-table";
import type { ListSort } from "@/lib/list-sort";
import { priceRange, productStateLabel, type ProductRow } from "../logic/catalog-page";
import styles from "../catalog-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";

const count = (value: number | null | undefined) => (value === null || value === undefined ? EMPTY_TEXT : String(value));

/**
 * 列宽：商品（名称 + ID 两行）给得最宽，名称、类目都单行截断、悬停看全文；
 * 价格 / 库存 / 销量右对齐、等宽数字，排在一起（价格区间放不下时折成两行）。商品名、类目是文本，不排序。
 * 列宽之和（含序号）928，1280 宽的窗口里不横向滚动。
 */
const columns: DataColumn<ProductRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 88, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  {
    key: "name", label: "商品", width: 192,
    render: (_, row) => {
      const name = row.name ?? "未命名商品";
      return (
        <span className={styles.productCell}>
          <span className={`cell-ellipsis ${styles.productName}`} title={name}>{name}</span>
          <span className={`cell-ellipsis ${styles.muted}`}>{row.product_id}</span>
        </span>
      );
    },
  },
  {
    key: "category", label: "类目", width: 104,
    render: (_, row) => {
      const text = row.display.category_name ?? EMPTY_TEXT;
      return <span className="cell-ellipsis" title={row.display.category_name ?? undefined}>{text}</span>;
    },
  },
  { key: "tab", label: "状态", sortable: true, width: 80, render: (_, row) => productStateLabel(row) },
  { key: "price", label: "价格", sortable: true, numeric: true, width: 128, render: (_, row) => priceRange(row) },
  { key: "stock_num", label: "库存", sortable: true, numeric: true, width: 80, render: (v) => count(v as number | null) },
  { key: "sell_num", label: "销量", sortable: true, numeric: true, width: 80, render: (v) => count(v as number | null) },
  { key: "sell_num_30d", label: "30 天销量", sortable: true, numeric: true, width: 112, render: (_, row) => count(row.display.sell_num_30d) },
];

interface ProductTableProps {
  rows: ProductRow[];
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

/** 快照列表：点表头改 URL 里的排序，由服务端排好再分页（默认按销量倒序）。 */
export function ProductTable({ rows, sort, onSortChange, seqOffset }: ProductTableProps) {
  return (
    <DataTable<ProductRow>
      rows={rows}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="商品列表"
      emptyMessage="没有符合条件的商品"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

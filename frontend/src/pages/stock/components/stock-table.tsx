import { Badge } from "@/components/arc/badge/badge";
import { TIME_COL_WIDTH } from "@/lib/table-columns";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "@/components/custom/data-table/data-table";
import type { ListSort } from "@/lib/list-sort";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { stockBadge, type StockRow } from "../logic/stock-page";
import styles from "../stock-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";

const num = (value: number | null) => (value === null ? EMPTY_TEXT : String(value));

/** 列宽之和（含序号）934：1280 宽的窗口里不横向滚动；商品名与 ID 单行截断、悬停看全文。 */
const columns: DataColumn<StockRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 84, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  {
    key: "name", label: "商品", width: 152,
    render: (_, row) => {
      const name = row.name ?? `商品 ${row.product_id}`;
      return (
        <span className={styles.productCell}>
          <span className="cell-ellipsis" title={name}>{name}</span>
          <span className={`cell-ellipsis ${styles.muted}`}>{row.product_id}</span>
        </span>
      );
    },
  },
  { key: "total_stock_num", label: "总库存", sortable: true, numeric: true, width: 94,
    render: (v) => num(v as number | null) },
  { key: "spot_stock_num", label: "现货", sortable: true, numeric: true, width: 80,
    render: (v) => num(v as number | null) },
  // 现货与未来库存是两套库存，分列展示，界面不提供相加（附录 D.4 第 2 条）
  { key: "future_stock_num", label: "未来库存", sortable: true, numeric: true, width: 106,
    render: (v) => num(v as number | null) },
  { key: "total_occupied_stock_num", label: "占用", sortable: true, numeric: true, width: 80,
    render: (v) => num(v as number | null) },
  { key: "total_unoccupied_stock_num", label: "未占用", sortable: true, numeric: true, width: 94,
    render: (v) => num(v as number | null) },
  {
    key: "status", label: "状态", sortable: true, width: 80,
    render: (_, row) => {
      const badge = stockBadge(row);
      return <Badge tone={badge.tone} dot>{badge.label}</Badge>;
    },
  },
  {
    key: "synced_at", label: "数据时间", sortable: true, width: TIME_COL_WIDTH,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];
interface StockTableProps {
  rows: StockRow[];
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

/** 库存快照列表：点表头改 URL 里的排序，由服务端排好再分页（默认按总库存升序，缺货的在前）。 */
export function StockTable({ rows, sort, onSortChange, seqOffset }: StockTableProps) {
  return (
    <DataTable<StockRow>
      rows={rows}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="库存列表"
      emptyMessage="没有符合条件的库存记录"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

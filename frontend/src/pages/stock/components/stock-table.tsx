import { Badge } from "@/components/arc/badge/badge";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { stockBadge, type StockRow } from "../logic/stock-page";
import styles from "../stock-page.module.css";

const num = (value: number | null) => (value === null ? "暂无" : String(value));

const columns: DataColumn<StockRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 110 },
  {
    key: "name", label: "商品", sortable: false, width: 240,
    render: (_, row) => (
      <span className={styles.productCell}>
        <span>{row.name ?? `商品 ${row.product_id}`}</span>
        <span className={styles.muted}>{row.product_id}</span>
      </span>
    ),
  },
  { key: "total_stock_num", label: "总库存", sortable: false, numeric: true, width: 100,
    render: (v) => num(v as number | null) },
  { key: "spot_stock_num", label: "现货", sortable: false, numeric: true, width: 90,
    render: (v) => num(v as number | null) },
  // 现货与未来库存是两套库存，分列展示，界面不提供相加（附录 D.4 第 2 条）
  { key: "future_stock_num", label: "未来库存", sortable: false, numeric: true, width: 100,
    render: (v) => num(v as number | null) },
  { key: "total_occupied_stock_num", label: "占用", sortable: false, numeric: true, width: 90,
    render: (v) => num(v as number | null) },
  { key: "total_unoccupied_stock_num", label: "未占用", sortable: false, numeric: true, width: 100,
    render: (v) => num(v as number | null) },
  {
    key: "status", label: "状态", sortable: false, width: 90,
    render: (_, row) => {
      const badge = stockBadge(row);
      return <Badge tone={badge.tone} dot>{badge.label}</Badge>;
    },
  },
  {
    key: "synced_at", label: "数据时间", sortable: false, width: 140,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];

/** 库存快照列表：服务端分页，预警行排在前面。 */
export function StockTable({ rows }: { rows: StockRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<StockRow>
        rows={rows}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="库存列表"
        emptyMessage="没有符合条件的库存记录；先点「同步库存」拉取快照"
      />
    </div>
  );
}

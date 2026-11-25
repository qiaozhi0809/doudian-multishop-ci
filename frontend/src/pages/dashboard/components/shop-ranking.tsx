import { Badge } from "@/components/arc/badge/badge";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { formatCents } from "@/lib/money-format";
import type { RankingRow } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

const numberText = (value: unknown): string => (value === null || value === undefined ? "暂无" : String(value));

const columns: DataColumn<RankingRow>[] = [
  { key: "name", label: "店铺", sortable: true, width: 140 },
  {
    key: "stateText",
    label: "会话",
    sortable: false,
    width: 110,
    render: (_, row) => <Badge tone={row.stateTone}>{row.stateText}</Badge>,
  },
  { key: "stockUp", label: "待发货", sortable: true, numeric: true, width: 90, render: numberText },
  { key: "expShip", label: "24 小时内须发", sortable: true, numeric: true, width: 120, render: numberText },
  { key: "shipDelay", label: "超时未发", sortable: true, numeric: true, width: 100, render: numberText },
  { key: "aftersalePending", label: "售后待办", sortable: true, numeric: true, width: 100, render: numberText },
  { key: "onsale", label: "在售商品", sortable: true, numeric: true, width: 100, render: numberText },
  {
    key: "unsettledCents",
    label: "待结算",
    sortable: true,
    numeric: true,
    width: 120,
    render: (value) => (value === null || value === undefined ? "暂无" : formatCents(value as number)),
  },
];

/** 店铺排行：按待发货降序，可排序；未取到数据的格子显示「暂无」，不静默当 0。 */
export function ShopRanking({ rows }: { rows: RankingRow[] }) {
  return (
    <section className={styles.tableCard}>
      <h2 className={styles.sectionTitle}>店铺排行</h2>
      <div className={styles.tableWrap}>
        <SortableDataTable<RankingRow>
          rows={rows}
          columns={columns}
          rowKey={(row) => String(row.shopId)}
          caption="店铺排行"
          emptyMessage="还没有店铺"
          defaultSort={{ key: "stockUp", direction: "desc" }}
        />
      </div>
    </section>
  );
}

import { Badge } from "@/components/arc/badge/badge";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { itemSummary, localStatusBadge, platformStatusText } from "../logic/order-columns";
import styles from "../order-page.module.css";
import { OrderNoCell } from "./order-no-cell";

type OrderRow = components["schemas"]["OrderRow"];

const TimeCell = ({ iso }: { iso: string | null }) => (
  <span className={styles.tabular} title={formatBjTime(iso)}>
    {formatBjTimeSmart(iso)}
  </span>
);

function LocalStatusCell({ row }: { row: OrderRow }) {
  const badge = localStatusBadge(row.status);
  const el = (
    <Badge tone={badge.tone} dot>
      {badge.label}
    </Badge>
  );
  if (row.status !== "exception" || !row.exception_reason) return el;
  return (
    <Tooltip content={row.exception_reason}>
      <span tabIndex={0}>{el}</span>
    </Tooltip>
  );
}

/** 列表按页从服务端取，客户端排序只会误导，所以所有列都不可排序。 */
const columns: DataColumn<OrderRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 140 },
  { key: "order_no", label: "订单号", sortable: false, width: 190, render: (v) => <OrderNoCell value={String(v)} /> },
  { key: "platform_status", label: "平台状态", sortable: false, width: 100, render: (v) => <span className={styles.muted}>{platformStatusText(v as number | null)}</span> },
  { key: "status", label: "本地状态", sortable: false, width: 110, render: (_, row) => <LocalStatusCell row={row} /> },
  { key: "amount_cents", label: "实付", sortable: false, numeric: true, width: 110, render: (v) => (v === null ? "暂无" : formatCents(v as number)) },
  { key: "pay_time", label: "支付时间", sortable: false, width: 140, render: (v) => <TimeCell iso={v as string | null} /> },
  { key: "exp_ship_time", label: "承诺发货时间", sortable: false, width: 140, render: (v) => <TimeCell iso={v as string | null} /> },
  { key: "items", label: "商品", sortable: false, width: 220, render: (_, row) => itemSummary(row.items) },
];

export function OrderTable({ rows }: { rows: OrderRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<OrderRow>
        rows={rows}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="订单列表"
        emptyMessage="没有符合条件的订单"
      />
    </div>
  );
}

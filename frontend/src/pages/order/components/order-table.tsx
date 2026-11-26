import { Badge } from "@/components/arc/badge/badge";
import { ID_COL_WIDTH, TIME_COL_WIDTH } from "@/lib/table-columns";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "@/components/custom/data-table/data-table";
import type { ListSort } from "@/lib/list-sort";
import type { components } from "@/lib/api-types";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { itemSummary, localStatusBadge, platformStatusText } from "../logic/order-columns";
import styles from "../order-page.module.css";
import { OrderNoCell } from "./order-no-cell";
import { EMPTY_TEXT } from "@/lib/empty-text";

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

/** 分页列表：点表头改 URL 里的排序，由服务端排好再分页（默认按支付时间倒序）；商品摘要是长文本，不排序。 */
const columns: DataColumn<OrderRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 100, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  { key: "order_no", label: "订单号", width: ID_COL_WIDTH, render: (v) => <OrderNoCell value={String(v)} /> },
  { key: "platform_status", label: "平台状态", sortable: true, width: 106, render: (v) => <span className={styles.muted}>{platformStatusText(v as number | null)}</span> },
  { key: "status", label: "本地状态", sortable: true, width: 106, render: (_, row) => <LocalStatusCell row={row} /> },
  { key: "amount_cents", label: "实付", sortable: true, numeric: true, width: 90, render: (v) => (v === null ? EMPTY_TEXT : formatCents(v as number)) },
  { key: "pay_time", label: "支付时间", sortable: true, width: TIME_COL_WIDTH, render: (v) => <TimeCell iso={v as string | null} /> },
  { key: "exp_ship_time", label: "承诺发货时间", sortable: true, width: TIME_COL_WIDTH, render: (v) => <TimeCell iso={v as string | null} /> },
  {
    key: "items", label: "商品", width: 146,
    render: (_, row) => {
      const text = itemSummary(row.items);
      return <span className="cell-ellipsis" title={text}>{text}</span>;
    },
  },
];

interface OrderTableProps {
  rows: OrderRow[];
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

export function OrderTable({ rows, sort, onSortChange, seqOffset }: OrderTableProps) {
  return (
    <DataTable<OrderRow>
      rows={rows}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="订单列表"
      emptyMessage="没有符合条件的订单"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

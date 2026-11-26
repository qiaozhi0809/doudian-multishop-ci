import { Badge } from "@/components/arc/badge/badge";
import { ID_COL_WIDTH, TIME_COL_WIDTH } from "@/lib/table-columns";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "@/components/custom/data-table/data-table";
import type { ListSort } from "@/lib/list-sort";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { deadlineInfo, statusLabel, typeLabel, type AftersaleRow } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";

const columns: DataColumn<AftersaleRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 100, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  {
    key: "after_sale_id", label: "售后单号", width: ID_COL_WIDTH,
    render: (v) => <span className={styles.tabular}>{String(v)}</span>,
  },
  {
    key: "order_no", label: "订单号", width: ID_COL_WIDTH,
    render: (v) => (v ? <span className={styles.tabular}>{String(v)}</span> : EMPTY_TEXT),
  },
  { key: "type", label: "类型", sortable: true, width: 80, render: (_, row) => typeLabel(row) },
  { key: "status", label: "状态", sortable: true, width: 100, render: (_, row) => statusLabel(row) },
  {
    key: "refund_amount_cents", label: "退款金额", sortable: true, numeric: true, width: 108,
    render: (v) => (v === null ? EMPTY_TEXT : formatCents(v as number)),
  },
  {
    key: "apply_time", label: "申请时间", sortable: true, width: TIME_COL_WIDTH,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string | null)}>
        {formatBjTimeSmart(v as string | null)}
      </span>
    ),
  },
  {
    key: "status_deadline", label: "处理截止", sortable: true, width: 108,
    render: (_, row) => {
      const info = deadlineInfo(row.status_deadline);
      if (info.tone === "neutral") return <span className={styles.muted}>{info.text}</span>;
      return (
        <Badge tone={info.tone} dot>
          {info.text}
        </Badge>
      );
    },
  },
  {
    key: "buyer", label: "买家", width: 90,
    render: (_, row) => <span className="cell-ellipsis" title={row.display.buyer_nick ?? undefined}>{row.display.buyer_nick ?? EMPTY_TEXT}</span>,
  },
  {
    key: "intervene", label: "平台介入", width: 80,
    render: (_, row) =>
      row.display.platform_intervene ? <Badge tone="warning">介入</Badge> : EMPTY_TEXT,
  },
];
interface AftersaleTableProps {
  rows: AftersaleRow[];
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

/** 分页列表：点表头改 URL 里的排序，由服务端排好再分页（默认待办按截止时间、全部按申请时间）。 */
export function AftersaleTable({ rows, sort, onSortChange, seqOffset }: AftersaleTableProps) {
  return (
    <DataTable<AftersaleRow>
      rows={rows}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="售后列表"
      emptyMessage="没有符合条件的售后单"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

import { Badge } from "@/components/arc/badge/badge";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { deadlineInfo, statusLabel, typeLabel, type AftersaleRow } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";

const columns: DataColumn<AftersaleRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 120 },
  {
    key: "after_sale_id", label: "售后单号", sortable: false, width: 190,
    render: (v) => <span className={styles.tabular}>{String(v)}</span>,
  },
  {
    key: "order_no", label: "订单号", sortable: false, width: 190,
    render: (v) => (v ? <span className={styles.tabular}>{String(v)}</span> : "—"),
  },
  { key: "type", label: "类型", sortable: false, width: 100, render: (_, row) => typeLabel(row) },
  { key: "status", label: "状态", sortable: false, width: 120, render: (_, row) => statusLabel(row) },
  {
    key: "refund_amount_cents", label: "退款金额", sortable: false, numeric: true, width: 110,
    render: (v) => (v === null ? "暂无" : formatCents(v as number)),
  },
  {
    key: "apply_time", label: "申请时间", sortable: false, width: 140,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string | null)}>
        {formatBjTimeSmart(v as string | null)}
      </span>
    ),
  },
  {
    key: "status_deadline", label: "处理截止", sortable: false, width: 120,
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
    key: "buyer", label: "买家", sortable: false, width: 100,
    render: (_, row) => row.display.buyer_nick ?? "—",
  },
  {
    key: "intervene", label: "平台介入", sortable: false, width: 100,
    render: (_, row) =>
      row.display.platform_intervene ? <Badge tone="warning">介入</Badge> : "—",
  },
];

/** 列表由服务端分页与排序（待办按截止时间、全部按申请时间），客户端不再排序。 */
export function AftersaleTable({ rows }: { rows: AftersaleRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<AftersaleRow>
        rows={rows}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="售后列表"
        emptyMessage="没有符合条件的售后单"
      />
    </div>
  );
}

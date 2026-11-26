import { EMPTY_TEXT } from "@/lib/empty-text";
import { Badge } from "@/components/arc/badge/badge";
import { ID_COL_WIDTH, TIME_COL_WIDTH } from "@/lib/table-columns";
import { Button } from "@/components/arc/button/button";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { DataTable } from "@/components/custom/data-table/data-table";
import { OrderNoCell } from "@/components/custom/order-no-cell/order-no-cell";
import type { ListSort } from "@/lib/list-sort";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { kindTone, trackingPair, type Finding } from "../logic/reconcile-view";
import styles from "../reconcile-page.module.css";

interface FindingsTableProps {
  rows: Finding[];
  marking: boolean;
  onMarkHandled: (id: number) => void;
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

/** 对账异常表：三类异常按 kind 着色，未处理的可一键标记。点表头改 URL 里的排序，由服务端排好再分页（默认最新发现的在前）。 */
export function FindingsTable({ rows, marking, onMarkHandled, sort, onSortChange, seqOffset }: FindingsTableProps) {
  const columns: DataColumn<Finding>[] = [
    { key: "shop_name", label: "店铺", sortable: true, width: 100, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
    { key: "shop_order_id", label: "订单号", width: ID_COL_WIDTH, render: (v) => <OrderNoCell value={v as string} /> },
    {
      key: "kind", label: "异常", sortable: true, width: 120,
      render: (_, row) => (
        <span title={row.detail ?? undefined}>
          <Badge tone={kindTone(row.kind)} dot>{row.kind_title}</Badge>
        </span>
      ),
    },
    {
      key: "tracking", label: "运单号（本地 → 平台）", width: 220,
      render: (_, row) => {
        const text = trackingPair(row);
        return <span className={`cell-ellipsis ${styles.waybill}`} title={text}>{text}</span>;
      },
    },
    {
      key: "status_change", label: "状态变化", width: 110,
      render: (_, row) => <span className={styles.muted}>{row.local_status ?? EMPTY_TEXT} → {row.platform_status ?? EMPTY_TEXT}</span>,
    },
    {
      key: "created_at", label: "发现时间", sortable: true, width: TIME_COL_WIDTH,
      render: (v) => <span className={styles.tabular} title={formatBjTime(v as string)}>{formatBjTimeSmart(v as string)}</span>,
    },
    {
      key: "status", label: "处理状态", sortable: true, width: 106,
      render: (v) => (v === "handled" ? <Badge tone="success" dot>已处理</Badge> : <Badge tone="warning" dot>未处理</Badge>),
    },
    {
      key: "actions", label: "操作", width: 120,
      render: (_, row) => {
        const handled = row.status === "handled";
        const action = (
          <Button variant="secondary" size="sm" disabled={handled || marking} onClick={() => onMarkHandled(row.id)}>
            标记已处理
          </Button>
        );
        if (!handled) return action;
        // 禁用元素收不到悬停和焦点，原因挂在外层 span 上
        return (
          <Tooltip content="这条已处理">
            <span className={styles.tip} tabIndex={0}>{action}</span>
          </Tooltip>
        );
      },
    },
  ];
  return (
    <DataTable<Finding>
      rows={rows}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="发货异常"
      emptyMessage="没有符合条件的发货异常"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

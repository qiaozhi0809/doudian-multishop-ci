import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { formatBjTime } from "@/lib/time-format";
import type { PoolItem } from "../hooks/use-proxy-pool";
import { poolStatus, type PoolTone } from "../logic/pool-status";
import styles from "../proxy-pool-page.module.css";

interface PoolTableProps {
  items: PoolItem[];
  pendingIds: number[];
  onCheck: (item: PoolItem) => void;
  onEdit: (item: PoolItem) => void;
  onDelete: (item: PoolItem) => void;
}

const BADGE_TONE = { success: "success", info: "info", danger: "danger", muted: "neutral" } as const satisfies Record<PoolTone, string>;

function StatusCell({ item }: { item: PoolItem }) {
  const status = poolStatus(item);
  return (
    <Badge tone={BADGE_TONE[status.tone]} dot>
      {status.label}
    </Badge>
  );
}

function CheckedCell({ item }: { item: PoolItem }) {
  if (!item.last_checked_at) return <span className={styles.muted}>未检测</span>;
  return (
    <span className={styles.tabular}>
      {formatBjTime(item.last_checked_at)}
      {item.last_check_ip ? <span className={styles.muted}>{` · ${item.last_check_ip}`}</span> : null}
    </span>
  );
}

/** 代理池表格：代理 / 到期日 / 状态 / 上次检测 / 操作。 */
export function PoolTable({ items, pendingIds, onCheck, onEdit, onDelete }: PoolTableProps) {
  const columns: DataColumn<PoolItem>[] = [
    { key: "proxy_display", label: "代理", sortable: false, width: 160, render: (v) => <span className={styles.proxy}>{String(v)}</span> },
    { key: "expires_at", label: "到期日", sortable: true, width: 110, render: (v) => <span className={styles.tabular}>{v ? String(v) : "不限"}</span> },
    { key: "expiry_state", label: "状态", sortable: false, width: 150, render: (_, row) => <StatusCell item={row} /> },
    { key: "last_checked_at", label: "上次检测", sortable: false, width: 200, render: (_, row) => <CheckedCell item={row} /> },
    {
      key: "actions",
      label: "操作",
      sortable: false,
      width: 190,
      render: (_, row) => {
        const busy = pendingIds.includes(row.id);
        return (
          <div className={styles.actions}>
            <Button variant="secondary" size="sm" loading={busy} onClick={() => onCheck(row)}>
              检测
            </Button>
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => onEdit(row)}>
              编辑
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => onDelete(row)}>
              删除
            </Button>
          </div>
        );
      },
    },
  ];
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<PoolItem>
        rows={items}
        columns={columns}
        rowKey={(row) => String(row.id)}
        caption="代理池"
        emptyMessage="代理池是空的"
      />
    </div>
  );
}

import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { DataTable, type TableColumn } from "@/components/custom/data-table/data-table";
import { RowMenu } from "@/components/custom/row-menu/row-menu";
import { formatBjTime } from "@/lib/time-format";
import type { PoolItem } from "../hooks/use-proxy-pool";
import { poolStatus, poolStatusSortValue, type PoolTone } from "../logic/pool-status";
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
  if (!item.last_checked_at) return <span className={styles.muted}>未检查</span>;
  return (
    <span className={styles.tabular}>
      {formatBjTime(item.last_checked_at)}
      {item.last_check_ip ? <span className={styles.muted}>{` · ${item.last_check_ip}`}</span> : null}
    </span>
  );
}

/** 代理池表格（一次全量返回，前端排序）：序号 / 代理 / 到期日 / 状态 / 上次检查 / 操作（行内只露「检查」，编辑、删除收进「⋯」）。 */
export function PoolTable({ items, pendingIds, onCheck, onEdit, onDelete }: PoolTableProps) {
  const columns: TableColumn<PoolItem>[] = [
    { key: "proxy_display", label: "代理", width: 160, render: (v) => <span className={styles.proxy}>{String(v)}</span> },
    { key: "expires_at", label: "到期日", sortable: true, width: 110, render: (v) => <span className={styles.tabular}>{v ? String(v) : "不限期"}</span> },
    { key: "expiry_state", label: "状态", sortable: true, width: 150, sortValue: poolStatusSortValue, render: (_, row) => <StatusCell item={row} /> },
    { key: "last_checked_at", label: "上次检查", sortable: true, width: 200, render: (_, row) => <CheckedCell item={row} /> },
    {
      key: "actions",
      label: "操作",
      width: 110,
      render: (_, row) => {
        const busy = pendingIds.includes(row.id);
        return (
          <div className={styles.actions}>
            <Button variant="secondary" size="sm" loading={busy} onClick={() => onCheck(row)}>
              检查
            </Button>
            <RowMenu
              items={[
                { label: "编辑", onSelect: () => onEdit(row), disabled: busy },
                { label: "删除", onSelect: () => onDelete(row), disabled: busy, destructive: true, separatorBefore: true },
              ]}
            />
          </div>
        );
      },
    },
  ];
  return (
    <DataTable<PoolItem>
      rows={items}
      columns={columns}
      rowKey={(row) => String(row.id)}
      caption="代理池"
      emptyMessage="没有符合条件的代理"
    />
  );
}

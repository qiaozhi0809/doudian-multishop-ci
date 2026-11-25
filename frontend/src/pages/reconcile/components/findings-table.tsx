import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { formatBjTimeSmart } from "@/lib/time-format";
import { kindTone, trackingPair, type Finding } from "../logic/reconcile-view";
import styles from "../reconcile-page.module.css";

interface FindingsTableProps {
  rows: Finding[];
  marking: boolean;
  onMarkHandled: (id: number) => void;
}

/** 对账异常表：三类异常按 kind 着色，未处理的可一键标记。 */
export function FindingsTable({ rows, marking, onMarkHandled }: FindingsTableProps) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.srOnly}>发货异常</caption>
        <thead>
          <tr>
            <th>店铺</th>
            <th>订单号</th>
            <th>异常</th>
            <th>运单号（本地 → 平台）</th>
            <th>状态变化</th>
            <th>发现时间</th>
            <th>处理状态</th>
            <th className={styles.opCol}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className={styles.emptyCell}>没有符合条件的发货异常</td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.id}>
                <td>{row.shop_name}</td>
                <td className={styles.tabular}>{row.shop_order_id}</td>
                <td title={row.detail ?? undefined}>
                  <Badge tone={kindTone(row.kind)} dot>{row.kind_title}</Badge>
                </td>
                <td className={styles.waybill}>{trackingPair(row)}</td>
                <td className={styles.muted}>
                  {row.local_status ?? "无"} → {row.platform_status ?? "无"}
                </td>
                <td className={styles.tabular}>{formatBjTimeSmart(row.created_at)}</td>
                <td>
                  {row.status === "handled" ? (
                    <Badge tone="success" dot>已处理</Badge>
                  ) : (
                    <Badge tone="warning" dot>未处理</Badge>
                  )}
                </td>
                <td>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={row.status === "handled" || marking}
                    onClick={() => onMarkHandled(row.id)}
                  >
                    标记已处理
                  </Button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

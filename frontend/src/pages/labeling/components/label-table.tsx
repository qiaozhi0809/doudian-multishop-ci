import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { Checkbox } from "@/components/arc/checkbox/checkbox";
import { formatCents } from "@/lib/money-format";
import { formatBjTimeSmart } from "@/lib/time-format";
import {
  canSelect,
  itemSummary,
  rowStatusBadge,
  type LabelOrder,
} from "../logic/label-columns";
import styles from "../labeling-page.module.css";


interface LabelTableProps {
  rows: LabelOrder[];
  selected: ReadonlySet<number>;
  allChecked: boolean;
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  onReceiver: (id: number) => void;
}

function WaybillCell({ row }: { row: LabelOrder }) {
  if (row.waybill) {
    return (
      <span className={styles.waybill}>
        {row.waybill.courier_code} · <span className={styles.tabular}>{row.waybill.waybill_no ?? "暂无"}</span>
      </span>
    );
  }
  if (row.blocked_reason) {
    return <span className={styles.blocked} title={row.blocked_reason}>{row.blocked_reason}</span>;
  }
  return <span className={styles.muted}>暂无</span>;
}

/** 打单台表格：首列勾选，阻断行禁用勾选并显示原因（跨页勾选由外部状态维护）。 */
export function LabelTable({
  rows,
  selected,
  allChecked,
  onToggle,
  onToggleAll,
  onReceiver,
}: LabelTableProps) {
  const someSelected = selected.size > 0 && !allChecked;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.srOnly}>打单台订单池</caption>
        <thead>
          <tr>
            <th className={styles.checkCol}>
              <Checkbox
                checked={allChecked ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={onToggleAll}
                aria-label="全选本页可勾选订单"
              />
            </th>
            <th>店铺</th>
            <th>订单号</th>
            <th>本地状态</th>
            <th>商品</th>
            <th className={styles.numeric}>实付</th>
            <th>支付时间</th>
            <th>面单 / 阻断原因</th>
            <th className={styles.opCol}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={9} className={styles.emptyCell}>没有符合条件的订单</td>
            </tr>
          ) : (
            rows.map((row) => {
              const badge = rowStatusBadge(row.status);
              return (
                <tr key={row.id} data-blocked={!canSelect(row)}>
                  <td>
                    <Checkbox
                      checked={selected.has(row.id)}
                      disabled={!canSelect(row)}
                      onCheckedChange={() => onToggle(row.id)}
                      aria-label={`选择订单 ${row.order_no}`}
                    />
                  </td>
                  <td>{row.shop_name}</td>
                  <td className={styles.tabular}>{row.order_no}</td>
                  <td><Badge tone={badge.tone} dot>{badge.label}</Badge></td>
                  <td>{itemSummary(row.items)}</td>
                  <td className={styles.numeric}>
                    {row.amount_cents === null ? "暂无" : formatCents(row.amount_cents)}
                  </td>
                  <td className={styles.tabular}>{formatBjTimeSmart(row.pay_time)}</td>
                  <td><WaybillCell row={row} /></td>
                  <td>
                    <Button variant="ghost" size="sm" onClick={() => onReceiver(row.id)}>
                      查看收件人
                    </Button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

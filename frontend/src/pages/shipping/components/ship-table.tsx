import { Badge } from "@/components/arc/badge/badge";
import { Checkbox } from "@/components/arc/checkbox/checkbox";
import { formatCents } from "@/lib/money-format";
import { formatBjTimeSmart } from "@/lib/time-format";
import { canSelect, rowStatusLabel, type ShipOrder } from "../logic/ship-columns";
import styles from "../shipping-page.module.css";

interface ShipTableProps {
  rows: ShipOrder[];
  selected: ReadonlySet<number>;
  allChecked: boolean;
  onToggle: (id: number) => void;
  onToggleAll: () => void;
}

function StatusBadge({ row }: { row: ShipOrder }) {
  return row.status === "printed" ? (
    <Badge tone="success" dot>{rowStatusLabel(row)}</Badge>
  ) : (
    <Badge tone="info" dot>{rowStatusLabel(row)}</Badge>
  );
}

/** 发货台表格：首列勾选，运单号缺失的行禁用勾选并提示。 */
export function ShipTable({ rows, selected, allChecked, onToggle, onToggleAll }: ShipTableProps) {
  const someSelected = selected.size > 0 && !allChecked;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.srOnly}>待发货订单</caption>
        <thead>
          <tr>
            <th className={styles.checkCol}>
              <Checkbox
                checked={allChecked ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={onToggleAll}
                aria-label="全选本页可发货订单"
              />
            </th>
            <th>店铺</th>
            <th>订单号</th>
            <th>本地状态</th>
            <th className={styles.numeric}>实付</th>
            <th>支付时间</th>
            <th>快递 / 运单号</th>
            <th>最晚发货</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={8} className={styles.emptyCell}>没有待发货的订单</td>
            </tr>
          ) : (
            rows.map((row) => (
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
                <td><StatusBadge row={row} /></td>
                <td className={styles.numeric}>
                  {row.amount_cents === null ? "暂无" : formatCents(row.amount_cents)}
                </td>
                <td className={styles.tabular}>{formatBjTimeSmart(row.pay_time)}</td>
                <td className={styles.waybill}>
                  {row.courier_code} · <span className={styles.tabular}>{row.tracking_no}</span>
                </td>
                <td className={styles.tabular}>{formatBjTimeSmart(row.exp_ship_time)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

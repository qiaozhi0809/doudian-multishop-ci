import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { Checkbox } from "@/components/arc/checkbox/checkbox";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import {
  canSelect,
  itemSummary,
  rowStatusBadge,
  type LabelOrder,
} from "../logic/label-columns";
import { jobBadge, type WaybillPrint } from "../logic/print-status";
import styles from "../labeling-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";
import { SortHeader } from "@/components/custom/data-table/sort-header";
import type { ListSort } from "@/lib/list-sort";


interface LabelTableProps {
  rows: LabelOrder[];
  selected: ReadonlySet<number>;
  allChecked: boolean;
  onToggle: (id: number) => void;
  onToggleAll: () => void;
  onReceiver: (id: number) => void;
  printRows?: ReadonlyMap<number, WaybillPrint>;
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

function WaybillCell({ row, printRow }: { row: LabelOrder; printRow?: WaybillPrint }) {
  if (!row.waybill) {
    if (row.blocked_reason) {
      return <span className={styles.blocked} title={row.blocked_reason}>{row.blocked_reason}</span>;
    }
    return <span className={styles.muted}>{EMPTY_TEXT}</span>;
  }
  const badge = jobBadge(printRow?.job);
  const noPrintData = printRow !== undefined && !printRow.has_print_data && !badge;
  return (
    <span className={styles.waybillCell}>
      <span className={styles.waybill}>
        {row.waybill.courier_code} · <span className={styles.tabular}>{row.waybill.waybill_no ?? EMPTY_TEXT}</span>
      </span>
      {badge && <Badge tone={badge.tone} dot>{badge.label}</Badge>}
      {noPrintData && (
        <span className={styles.muted} title="打印时先补打，失败到抖店后台补打">
          无打印数据
        </span>
      )}
    </span>
  );
}

/**
 * 打单发货表格：首列勾选，阻断行禁用勾选并显示原因（跨页勾选由外部状态维护）。
 * 勾选之后是「序号」（翻页连续）；勾选 + 序号 + 店铺固定在左侧。点表头改 URL 里的排序，由服务端排好再分页。
 */
export function LabelTable({
  rows,
  selected,
  allChecked,
  onToggle,
  onToggleAll,
  onReceiver,
  printRows,
  sort,
  onSortChange,
  seqOffset,
}: LabelTableProps) {
  const someSelected = selected.size > 0 && !allChecked;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className={styles.srOnly}>打单发货订单池</caption>
        <thead>
          <tr>
            <th className={styles.checkCol}>
              <Checkbox
                checked={allChecked ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={onToggleAll}
                aria-label="全选本页可勾选订单"
              />
            </th>
            <th className={styles.seqCol}>序号</th>
            <SortHeader label="店铺" sortKey="shop_name" sort={sort} onSort={onSortChange} />
            <th>订单号</th>
            <SortHeader label="本地状态" sortKey="status" sort={sort} onSort={onSortChange} />
            <th>商品</th>
            <SortHeader label="实付" sortKey="amount_cents" sort={sort} onSort={onSortChange} numeric className={styles.numeric} />
            <SortHeader label="支付时间" sortKey="pay_time" sort={sort} onSort={onSortChange} />
            <th>面单 / 阻断原因</th>
            <th className={styles.opCol}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={10} className={styles.emptyCell}>没有符合条件的订单</td>
            </tr>
          ) : (
            rows.map((row, index) => {
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
                  <td className={styles.seqCol}>{seqOffset + index + 1}</td>
                  <td>{row.shop_name}</td>
                  <td className={styles.tabular}>{row.order_no}</td>
                  <td><Badge tone={badge.tone} dot>{badge.label}</Badge></td>
                  <td>
                    <span className={`cell-ellipsis ${styles.itemCell}`} title={itemSummary(row.items)}>{itemSummary(row.items)}</span>
                  </td>
                  <td className={styles.numeric}>
                    {row.amount_cents === null ? EMPTY_TEXT : formatCents(row.amount_cents)}
                  </td>
                  <td>
                    <span className={styles.tabular} title={formatBjTime(row.pay_time)}>{formatBjTimeSmart(row.pay_time)}</span>
                  </td>
                  <td><WaybillCell row={row} printRow={printRows?.get(row.waybill?.id ?? -1)} /></td>
                  <td>
                    <Button variant="secondary" size="sm" onClick={() => onReceiver(row.id)}>
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

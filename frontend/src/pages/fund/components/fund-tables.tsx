import { Badge } from "@/components/arc/badge/badge";
import { ID_COL_WIDTH, TIME_COL_WIDTH } from "@/lib/table-columns";
import { DataTable, type TableColumn } from "@/components/custom/data-table/data-table";
import type { ListSort } from "@/lib/list-sort";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import {
  billAmountText,
  billSummary,
  hasPendingAmount,
  marginLevelRank,
  marginLevelText,
  settlementDelayText,
  type BillItem,
  type MarginRow,
  type ShopBills,
  type UnsettledRow,
} from "../logic/fund-page";
import styles from "../fund-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";

const amount = (cents: number | null) => (cents === null ? EMPTY_TEXT : formatCents(cents));

const unsettledColumns: TableColumn<UnsettledRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 100, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  {
    key: "shop_order_no", label: "订单号", width: ID_COL_WIDTH,
    render: (v) => <span className={styles.tabular}>{String(v)}</span>,
  },
  {
    key: "product", label: "商品", width: 200,
    render: (_, row) => {
      const name = row.display.product_name ?? row.product_id ?? EMPTY_TEXT;
      return (
        <span className={styles.productCell}>
          <span className="cell-ellipsis" title={name}>{name}</span>
          {row.display.sku_detail_text && (
            <span className={`cell-ellipsis ${styles.muted}`} title={row.display.sku_detail_text}>
              {row.display.sku_detail_text}
            </span>
          )}
        </span>
      );
    },
  },
  { key: "income_amount_cents", label: "收入", sortable: true, numeric: true, width: 96,
    render: (v) => amount(v as number | null) },
  { key: "platform_service_fee_cents", label: "平台服务费", sortable: true, numeric: true, width: 122,
    render: (v) => amount(v as number | null) },
  { key: "unsettled_amount_cents", label: "待结算", sortable: true, numeric: true, width: 100,
    render: (v) => amount(v as number | null) },
  { key: "ecom_order_status", label: "订单状态", sortable: true, width: 106,
    render: (v) => (v ? String(v) : EMPTY_TEXT) },
  {
    key: "settlement", label: "结算条件", width: 160,
    render: (_, row) => {
      const text = settlementDelayText(row.display.settlement_delay_days);
      return <span className={`cell-ellipsis ${styles.muted}`} title={text}>{text}</span>;
    },
  },
  {
    key: "synced_at", label: "数据时间", sortable: true, width: TIME_COL_WIDTH,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];
interface UnsettledTableProps {
  rows: UnsettledRow[];
  sort: ListSort | null;
  onSortChange: (sort: ListSort) => void;
  seqOffset: number;
}

/** 待结算明细（本地快照）：点表头改 URL 里的排序，由服务端排好再分页（默认最近同步进来的在前）。 */
export function UnsettledTable({ rows, sort, onSortChange, seqOffset }: UnsettledTableProps) {
  return (
    <DataTable<UnsettledRow>
      rows={rows}
      columns={unsettledColumns}
      rowKey={(row) => String(row.id)}
      caption="待结算订单"
      emptyMessage="没有符合条件的待结算订单"
      sort={sort}
      onSortChange={onSortChange}
      serverSorted
      seqOffset={seqOffset}
    />
  );
}

const marginColumns: TableColumn<MarginRow>[] = [
  { key: "shop_name", label: "店铺", sortable: true, width: 110, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  { key: "payable_cents", label: "应付保证金", sortable: true, numeric: true, width: 122,
    render: (v) => amount(v as number | null) },
  { key: "balance_cents", label: "账户余额", sortable: true, numeric: true, width: 110,
    render: (v) => amount(v as number | null) },
  { key: "basic_payable_cents", label: "基础应付", sortable: true, numeric: true, width: 106,
    render: (v) => amount(v as number | null) },
  { key: "basic_balance_cents", label: "基础余额", sortable: true, numeric: true, width: 106,
    render: (v) => amount(v as number | null) },
  { key: "withdrawable_cents", label: "可提现", sortable: true, numeric: true, width: 100,
    render: (v) => amount(v as number | null) },
  { key: "level", label: "等级", sortable: true, width: 80, sortValue: (row) => marginLevelRank(row.level),
    render: (v) => marginLevelText(v as string | null) },
  {
    key: "synced_at", label: "数据时间", sortable: true, width: TIME_COL_WIDTH,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];
/** 保证金账户（按店唯一，一次全量返回）：前端排序，默认按店铺顺序。 */
export function MarginTable({ rows }: { rows: MarginRow[] }) {
  return (
    <DataTable<MarginRow>
      rows={rows}
      columns={marginColumns}
      rowKey={(row) => String(row.id)}
      caption="保证金账户"
      emptyMessage="没有符合条件的保证金记录"
    />
  );
}

type BillRow = BillItem & { row_key: string };

const billColumns: TableColumn<BillRow>[] = [
  { key: "summary", label: "摘要", width: 260,
    render: (_, row) => {
      const text = billSummary(row);
      return <span className="cell-ellipsis" title={text}>{text}</span>;
    } },
  {
    key: "amount_cents", label: "金额", sortable: true, numeric: true, width: 130,
    // 「待探明」的行金额是 0 占位，不参与大小比较，排在最后
    sortValue: (row) => (row.amount_status === "pending" ? null : row.amount_cents),
    render: (_, row) =>
      row.amount_status === "pending" ? (
        <Badge tone="warning" outline>待探明</Badge>
      ) : (
        billAmountText(row)
      ),
  },
  {
    key: "amount_field", label: "平台字段", width: 140,
    render: (v) => (v ? <span className={styles.tabular}>{String(v)}</span> : EMPTY_TEXT),
  },
];

/** 账单（上游实时，不落库，一次全量返回，前端排序）。金额字段未校准时标注「待探明」。 */
export function BillsTable({ shops, days, shopName }: { shops: ShopBills[]; days: number; shopName: (id: number) => string }) {
  const pending = hasPendingAmount(shops);
  return (
    <div className={styles.bills}>
      {pending && (
        <Badge tone="warning" outline>
          部分账单金额字段待探明：平台字段名未校准，金额显示为 0，拿到首笔账单后校准
        </Badge>
      )}
      {shops.map((shop) => (
        <section key={shop.shop_id} className="section" aria-label={`${shopName(shop.shop_id)} 账单`}>
          <header className={styles.billHeader}>
            <h3 className="section-title">{shopName(shop.shop_id)}</h3>
            {shop.source !== "upstream" ? (
              <Badge tone="danger" outline>{shop.error ?? "获取失败"}</Badge>
            ) : shop.total > 0 ? (
              <Badge tone="neutral" outline>{shop.total} 条</Badge>
            ) : null}
            {shop.fetched_at && (
              <span className={styles.muted} title={formatBjTime(shop.fetched_at)}>
                取数 {formatBjTimeSmart(shop.fetched_at)}
              </span>
            )}
          </header>
          {shop.source === "upstream" && (
            <DataTable<BillRow>
              rows={(shop.items ?? []).map((item, index) => ({
                ...item,
                row_key: `${shop.shop_id}-${index}`,
              }))}
              columns={billColumns}
              rowKey={(row) => row.row_key}
              caption={`${shopName(shop.shop_id)} 账单`}
              emptyMessage={`近 ${days} 天没有账单`}
            />
          )}
        </section>
      ))}
    </div>
  );
}

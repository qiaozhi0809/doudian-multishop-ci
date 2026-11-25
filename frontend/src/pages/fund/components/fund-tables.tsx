import { Badge } from "@/components/arc/badge/badge";
import { SortableDataTable, type DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import {
  billAmountText,
  billSummary,
  hasPendingAmount,
  marginLevelText,
  settlementDelayText,
  type BillItem,
  type MarginRow,
  type ShopBills,
  type UnsettledRow,
} from "../logic/fund-page";
import styles from "../fund-page.module.css";

const amount = (cents: number | null) => (cents === null ? "暂无" : formatCents(cents));

const unsettledColumns: DataColumn<UnsettledRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 110 },
  {
    key: "shop_order_no", label: "订单号", sortable: false, width: 190,
    render: (v) => <span className={styles.tabular}>{String(v)}</span>,
  },
  {
    key: "product", label: "商品", sortable: false, width: 220,
    render: (_, row) => (
      <span className={styles.productCell}>
        <span>{row.display.product_name ?? row.product_id ?? "—"}</span>
        {row.display.sku_detail_text && (
          <span className={styles.muted}>{row.display.sku_detail_text}</span>
        )}
      </span>
    ),
  },
  { key: "income_amount_cents", label: "收入", sortable: false, numeric: true, width: 110,
    render: (v) => amount(v as number | null) },
  { key: "platform_service_fee_cents", label: "平台服务费", sortable: false, numeric: true, width: 110,
    render: (v) => amount(v as number | null) },
  { key: "unsettled_amount_cents", label: "待结算", sortable: false, numeric: true, width: 110,
    render: (v) => amount(v as number | null) },
  { key: "ecom_order_status", label: "订单状态", sortable: false, width: 100,
    render: (v) => (v ? String(v) : "—") },
  {
    key: "settlement", label: "结算条件", sortable: false, width: 200,
    render: (_, row) => (
      <span className={styles.muted}>{settlementDelayText(row.display.settlement_delay_days)}</span>
    ),
  },
  {
    key: "synced_at", label: "数据时间", sortable: false, width: 140,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];

/** 待结算明细（本地快照，服务端分页）。 */
export function UnsettledTable({ rows }: { rows: UnsettledRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<UnsettledRow>
        rows={rows}
        columns={unsettledColumns}
        rowKey={(row) => String(row.id)}
        caption="待结算订单"
        emptyMessage="没有待结算订单；先点「同步资金」拉取"
      />
    </div>
  );
}

const marginColumns: DataColumn<MarginRow>[] = [
  { key: "shop_name", label: "店铺", sortable: false, width: 130 },
  { key: "payable_cents", label: "应付保证金", sortable: false, numeric: true, width: 120,
    render: (v) => amount(v as number | null) },
  { key: "balance_cents", label: "账户余额", sortable: false, numeric: true, width: 120,
    render: (v) => amount(v as number | null) },
  { key: "basic_payable_cents", label: "基础应付", sortable: false, numeric: true, width: 120,
    render: (v) => amount(v as number | null) },
  { key: "basic_balance_cents", label: "基础余额", sortable: false, numeric: true, width: 120,
    render: (v) => amount(v as number | null) },
  { key: "withdrawable_cents", label: "可提现", sortable: false, numeric: true, width: 110,
    render: (v) => amount(v as number | null) },
  { key: "level", label: "等级", sortable: false, width: 90,
    render: (v) => marginLevelText(v as string | null) },
  {
    key: "synced_at", label: "数据时间", sortable: false, width: 140,
    render: (v) => (
      <span className={styles.tabular} title={formatBjTime(v as string)}>
        {formatBjTimeSmart(v as string)}
      </span>
    ),
  },
];

/** 保证金账户（按店唯一）。 */
export function MarginTable({ rows }: { rows: MarginRow[] }) {
  return (
    <div className={styles.tableWrap}>
      <SortableDataTable<MarginRow>
        rows={rows}
        columns={marginColumns}
        rowKey={(row) => String(row.id)}
        caption="保证金账户"
        emptyMessage="还没有保证金数据；先点「同步资金」拉取"
      />
    </div>
  );
}

type BillRow = BillItem & { row_key: string };

const billColumns: DataColumn<BillRow>[] = [
  {
    key: "amount_cents", label: "金额", sortable: false, numeric: true, width: 130,
    render: (_, row) =>
      row.amount_status === "pending" ? (
        <Badge tone="warning" outline>待探明</Badge>
      ) : (
        billAmountText(row)
      ),
  },
  {
    key: "amount_field", label: "平台字段", sortable: false, width: 140,
    render: (v) => (v ? <span className={styles.tabular}>{String(v)}</span> : "—"),
  },
  { key: "summary", label: "摘要", sortable: false, width: 260,
    render: (_, row) => billSummary(row) },
];

/** 账单（上游实时，不落库）。新店通常为空；金额字段未校准时标注「待探明」。 */
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
        <section key={shop.shop_id} className={styles.billShop} aria-label={`${shopName(shop.shop_id)} 账单`}>
          <header className={styles.billHeader}>
            <span className={styles.billShopName}>{shopName(shop.shop_id)}</span>
            {shop.source === "upstream" ? (
              <Badge tone="neutral" outline>{shop.total} 条</Badge>
            ) : (
              <Badge tone="danger" outline>{shop.error ?? "获取失败"}</Badge>
            )}
            {shop.fetched_at && (
              <span className={styles.muted} title={formatBjTime(shop.fetched_at)}>
                取数 {formatBjTimeSmart(shop.fetched_at)}
              </span>
            )}
          </header>
          {shop.source === "upstream" && (shop.items ?? []).length === 0 ? (
            <p className={styles.muted}>近 {days} 天没有账单（新店通常为空）</p>
          ) : (
            (shop.items ?? []).length > 0 && (
              <div className={styles.tableWrap}>
                <SortableDataTable<BillRow>
                  rows={(shop.items ?? []).map((item, index) => ({
                    ...item,
                    row_key: `${shop.shop_id}-${index}`,
                  }))}
                  columns={billColumns}
                  rowKey={(row) => row.row_key}
                  caption={`${shopName(shop.shop_id)} 账单`}
                  emptyMessage="没有账单"
                />
              </div>
            )
          )}
        </section>
      ))}
    </div>
  );
}

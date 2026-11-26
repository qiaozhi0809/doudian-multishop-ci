import { Badge } from "@/components/arc/badge/badge";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "@/components/custom/data-table/data-table";
import { formatCents } from "@/lib/money-format";
import type { RankingRow } from "../logic/dashboard";
import { EMPTY_TEXT } from "@/lib/empty-text";

const numberText = (value: unknown): string => (value === null || value === undefined ? EMPTY_TEXT : String(value));

/** 列宽之和（含序号）920：1280 宽的窗口里不横向滚动，可排序表头（文字 + 箭头）不截断。 */
const columns: DataColumn<RankingRow>[] = [
  { key: "name", label: "店铺", sortable: true, width: 120, render: (v) => <span className="cell-ellipsis" title={String(v)}>{String(v)}</span> },
  {
    key: "stateText",
    label: "会话",
    sortable: true,
    width: 96,
    render: (_, row) => <Badge tone={row.stateTone}>{row.stateText}</Badge>,
  },
  { key: "stockUp", label: "待发货", sortable: true, numeric: true, width: 94, render: numberText },
  { key: "expShip", label: "24 小时内须发", sortable: true, numeric: true, width: 136, render: numberText },
  { key: "shipDelay", label: "超时未发", sortable: true, numeric: true, width: 106, render: numberText },
  { key: "aftersalePending", label: "售后待办", sortable: true, numeric: true, width: 106, render: numberText },
  { key: "onsale", label: "在售商品", sortable: true, numeric: true, width: 106, render: numberText },
  {
    key: "unsettledCents",
    label: "待结算",
    sortable: true,
    numeric: true,
    width: 100,
    render: (value) => (value === null || value === undefined ? EMPTY_TEXT : formatCents(value as number)),
  },
];

/** 店铺排行（前端排序）：行已按待发货降序（logic/dashboard），点表头可改排序；默认排序不显示排序列底色，免得表头看着断成两段；未取到数据的格子显示「暂无」，不静默当 0。 */
export function ShopRanking({ rows }: { rows: RankingRow[] }) {
  return (
    <section className="section">
      <h2 className="section-title">店铺排行</h2>
      <DataTable<RankingRow>
        rows={rows}
        columns={columns}
        rowKey={(row) => String(row.shopId)}
        caption="店铺排行"
        emptyMessage="没有符合条件的店铺"
      />
    </section>
  );
}

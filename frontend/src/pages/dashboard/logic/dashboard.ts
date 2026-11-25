/** 仪表盘的纯聚合：把已有接口（订单计数 / 售后计数 / 资金 / 库存 / 商品计数）合成一份看板模型。 */

import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";

export type OrderCountsResponse = components["schemas"]["OrderCountsResponse"];
export type AftersaleCountsResponse = components["schemas"]["AftersaleCountsResponse"];
export type FundSummary = components["schemas"]["FundSummary"];
export type StockSummary = components["schemas"]["StockSummary"];
export type ProductCountsResponse = components["schemas"]["ProductCountsResponse"];

export type BadgeTone = "success" | "warning" | "danger" | "neutral";

export interface DashboardSources {
  shops: ShopRow[];
  orderCounts?: OrderCountsResponse;
  aftersaleCounts?: AftersaleCountsResponse;
  fund?: FundSummary;
  stock?: StockSummary;
  products?: ProductCountsResponse;
}

export interface DashboardKpis {
  activeShops: number;
  totalShops: number;
  stockUp: number;
  expShip: number;
  shipDelay: number;
  aftersalePending: number;
  unsettledCents: number;
  marginCents: number;
  alarmCount: number;
  soldOutCount: number;
  onsaleCount: number;
}

export type RankingRow = {
  shopId: number;
  name: string;
  stateText: string;
  stateTone: BadgeTone;
  stockUp: number | null;
  expShip: number | null;
  shipDelay: number | null;
  aftersalePending: number | null;
  onsale: number | null;
  unsettledCents: number | null;
};

export interface ChartBar {
  key: string;
  label: string;
  axisLabel?: string;
  value: number;
}

export interface SourceFailure {
  shopId: number;
  error: string | null;
}

export interface DashboardModel {
  kpis: DashboardKpis;
  ranking: RankingRow[];
  shipBars: ChartBar[];
  fundBars: ChartBar[];
  orderFailures: SourceFailure[];
  aftersaleFailures: SourceFailure[];
  productFailures: SourceFailure[];
  updatedAt: string | null;
}

const upstream = <T extends { source: string }>(shops: T[]): T[] => shops.filter((shop) => shop.source === "upstream");

function earliest(values: (string | null | undefined)[]): string | null {
  let result: string | null = null;
  for (const value of values) {
    if (value && (result === null || new Date(value) < new Date(result))) result = value;
  }
  return result;
}

/** 店铺会话状态（ui-guidelines 第 5 节文案与色调）。 */
export function shopState(shop: ShopRow): { text: string; tone: BadgeTone } {
  if (shop.status === "disabled") return { text: "已停用", tone: "neutral" };
  if (shop.status === "needs_login") return { text: "需重新登录", tone: "danger" };
  if (shop.paused_reason) return { text: "风控暂停", tone: "danger" };
  if (shop.egress_status === "unreachable" || shop.egress_status === "duplicate") {
    return { text: "出口异常", tone: "danger" };
  }
  if (shop.egress_status === "changed") return { text: "出口待确认", tone: "warning" };
  if (shop.health === "expiring") return { text: "即将过期", tone: "warning" };
  return { text: "正常", tone: "success" };
}

function shortLabel(name: string): string {
  return name.length > 5 ? `${name.slice(0, 5)}…` : name;
}

/** 取数值最高的前 N 家店（只含有非零值的店），用作柱状图数据。 */
export function topBars<T extends { shopId: number; name: string }>(
  rows: T[],
  value: (row: T) => number | null,
  limit = 10,
): ChartBar[] {
  return rows
    .map((row) => ({ row, value: value(row) ?? 0 }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, limit)
    .map(({ row, value: v }) => ({
      key: String(row.shopId),
      label: row.name,
      axisLabel: shortLabel(row.name),
      value: v,
    }));
}

export function buildDashboard(sources: DashboardSources): DashboardModel {
  const { shops, orderCounts, aftersaleCounts, fund, stock, products } = sources;

  const orderByShop = new Map((orderCounts?.shops ?? []).map((shop) => [shop.shop_id, shop]));
  const aftersaleByShop = new Map((aftersaleCounts?.shops ?? []).map((shop) => [shop.shop_id, shop]));
  const productByShop = new Map((products?.shops ?? []).map((shop) => [shop.shop_id, shop]));
  const fundByShop = new Map((fund?.shops ?? []).map((shop) => [shop.shop_id, shop]));

  const orderOk = upstream(orderCounts?.shops ?? []).filter((shop) => shop.counts !== null);
  const aftersaleOk = upstream(aftersaleCounts?.shops ?? []);
  const productOk = upstream(products?.shops ?? []).filter((shop) => shop.counts !== null);

  const kpis: DashboardKpis = {
    activeShops: shops.filter((shop) => shop.status === "active").length,
    totalShops: shops.length,
    stockUp: orderOk.reduce((sum, shop) => sum + (shop.counts?.stock_up ?? 0), 0),
    expShip: orderOk.reduce((sum, shop) => sum + (shop.counts?.exp_ship ?? 0), 0),
    shipDelay: orderOk.reduce((sum, shop) => sum + (shop.counts?.ship_delay ?? 0), 0),
    aftersalePending: aftersaleOk.reduce((sum, shop) => sum + shop.pending_total, 0),
    unsettledCents: fund?.total_unsettled_amount_cents ?? 0,
    marginCents: (fund?.shops ?? []).reduce((sum, shop) => sum + (shop.margin_balance_cents ?? 0), 0),
    alarmCount: stock?.alarm_count ?? 0,
    soldOutCount: stock?.sold_out_count ?? 0,
    onsaleCount: productOk.reduce((sum, shop) => sum + (shop.counts?.onsale ?? 0), 0),
  };

  const ranking: RankingRow[] = shops.map((shop) => {
    const order = orderByShop.get(shop.id);
    const aftersale = aftersaleByShop.get(shop.id);
    const product = productByShop.get(shop.id);
    const state = shopState(shop);
    return {
      shopId: shop.id,
      name: shop.name,
      stateText: state.text,
      stateTone: state.tone,
      stockUp: order?.source === "upstream" && order.counts ? order.counts.stock_up : null,
      expShip: order?.source === "upstream" && order.counts ? order.counts.exp_ship : null,
      shipDelay: order?.source === "upstream" && order.counts ? order.counts.ship_delay : null,
      aftersalePending: aftersale?.source === "upstream" ? aftersale.pending_total : null,
      onsale: product?.source === "upstream" && product.counts ? (product.counts.onsale ?? 0) : null,
      unsettledCents: fundByShop.get(shop.id)?.unsettled_amount_cents ?? null,
    };
  });
  ranking.sort((a, b) => (b.stockUp ?? -1) - (a.stockUp ?? -1) || a.name.localeCompare(b.name, "zh-CN"));

  const failures = (list: { shop_id: number; source: string; error?: string | null }[]): SourceFailure[] =>
    list.filter((shop) => shop.source !== "upstream").map((shop) => ({ shopId: shop.shop_id, error: shop.error ?? null }));

  return {
    kpis,
    ranking,
    shipBars: topBars(ranking, (row) => row.stockUp),
    fundBars: topBars(ranking, (row) => row.unsettledCents),
    orderFailures: failures(orderCounts?.shops ?? []),
    aftersaleFailures: failures(aftersaleCounts?.shops ?? []),
    productFailures: failures(products?.shops ?? []),
    updatedAt: earliest([
      ...orderOk.map((shop) => shop.fetched_at),
      ...aftersaleOk.map((shop) => shop.fetched_at),
      ...productOk.map((shop) => shop.fetched_at),
    ]),
  };
}

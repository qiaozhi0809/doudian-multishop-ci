import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { SHOP_FILTER_PARAM, serializeShopFilter } from "@/components/custom/app-shell/logic/shop-filter";
import { EMPTY_TEXT } from "@/lib/empty-text";
import { KpiDot, type KpiTone } from "@/lib/kpi-tone";
import { formatCents } from "@/lib/money-format";
import type { SectionState } from "../hooks/use-dashboard";
import type { DashboardKpis } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

/** 指标卡的跳转地址：页面路径 + 页面自己的参数 + 当前店铺范围。 */
export function kpiHref(path: string, shopIds: number[], extra: Record<string, string> = {}): string {
  const params = new URLSearchParams(extra);
  const shops = serializeShopFilter(shopIds);
  if (shops) params.set(SHOP_FILTER_PARAM, shops);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

interface KpiRowProps {
  label: string;
  tone: KpiTone;
  /** 数值文本（金额已格式化）；数字用于圆点在 0 时变灰。 */
  value: string;
  raw?: number;
  section?: SectionState;
  to: string;
}

/** 一行指标：圆点 名称 …… 数字（右对齐、等宽数字）。整行是链接；读取中显示骨架，出错显示「暂无」。 */
function KpiRow({ label, tone, value, raw, section, to }: KpiRowProps) {
  const state = section?.state ?? "ready";
  return (
    <li>
      <Link to={to} className={styles.kpiRow}>
        <span className={styles.kpiName}>
          <KpiDot tone={tone} value={state === "ready" ? raw : 0} />
          {label}
        </span>
        {state === "loading" ? (
          <span className={styles.kpiSkeleton}>
            <Skeleton label={`正在读取${label}`} lines={1} />
          </span>
        ) : (
          <span className={styles.kpiValue} data-empty={state === "error" || undefined}>
            {state === "error" ? EMPTY_TEXT : value}
          </span>
        )}
      </Link>
    </li>
  );
}

/** 一块指标卡片：标题在卡片内顶部，下面每个指标一行；组内从上到下越来越急。 */
function KpiPanel({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className={`panel ${styles.kpiPanel}`} role="group" aria-labelledby={`kpi-group-${id}`}>
      <h2 id={`kpi-group-${id}`} className="section-title">
        {title}
      </h2>
      <ul className={styles.kpiList}>{children}</ul>
    </section>
  );
}

const count = (value: number) => value.toLocaleString("zh-CN");

export function KpiGrid({
  kpis,
  sections,
}: {
  kpis: DashboardKpis;
  sections: {
    orderCounts: SectionState;
    aftersale: SectionState;
    fund: SectionState;
    stock: SectionState;
    products: SectionState;
  };
}) {
  const { shopIds } = useShopFilter();
  const href = (path: string, extra?: Record<string, string>) => kpiHref(path, shopIds, extra);
  return (
    <section aria-label="关键指标" className={styles.kpiPanels}>
      <KpiPanel id="ship" title="发货">
        <KpiRow label="待发货" tone="info" value={count(kpis.stockUp)} raw={kpis.stockUp} section={sections.orderCounts} to={href("/labeling")} />
        <KpiRow label="24 小时内须发" tone="warning" value={count(kpis.expShip)} raw={kpis.expShip} section={sections.orderCounts} to={href("/orders", { quick: "exp_ship" })} />
        <KpiRow label="超时未发" tone="danger" value={count(kpis.shipDelay)} raw={kpis.shipDelay} section={sections.orderCounts} to={href("/orders", { quick: "ship_delay" })} />
      </KpiPanel>
      <KpiPanel id="aftersale-stock" title="售后与库存">
        <KpiRow label="售后待办" tone="violet" value={count(kpis.aftersalePending)} raw={kpis.aftersalePending} section={sections.aftersale} to={href("/aftersale", { quick: "pending" })} />
        <KpiRow label="库存预警" tone="warning" value={count(kpis.alarmCount)} raw={kpis.alarmCount} section={sections.stock} to={href("/stock", { quick: "alarm" })} />
        <KpiRow label="售罄" tone="danger" value={count(kpis.soldOutCount)} raw={kpis.soldOutCount} section={sections.stock} to={href("/stock", { quick: "sold_out" })} />
      </KpiPanel>
      <KpiPanel id="shop-fund" title="店铺与资金">
        <KpiRow
          label="在营店铺"
          tone={kpis.activeShops < kpis.totalShops ? "warning" : "success"}
          value={`${kpis.activeShops} / ${kpis.totalShops}`}
          raw={kpis.totalShops - kpis.activeShops}
          to={href("/shops")}
        />
        <KpiRow label="在售商品" tone="success" value={count(kpis.onsaleCount)} raw={kpis.onsaleCount} section={sections.products} to={href("/catalog", { quick: "onsale" })} />
        <KpiRow label="待结算金额" tone="info" value={formatCents(kpis.unsettledCents)} raw={kpis.unsettledCents} section={sections.fund} to={href("/fund")} />
        <KpiRow label="保证金余额" tone="neutral" value={formatCents(kpis.marginCents)} raw={kpis.marginCents} section={sections.fund} to={href("/fund", { tab: "margin" })} />
      </KpiPanel>
    </section>
  );
}

import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { SHOP_FILTER_PARAM, serializeShopFilter } from "@/components/custom/app-shell/logic/shop-filter";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { Button } from "@/components/arc/button/button";
import { formatCents } from "@/lib/money-format";
import type { SectionState } from "../hooks/use-dashboard";
import type { DashboardKpis } from "../logic/dashboard";
import { KpiDot, type KpiTone } from "@/lib/kpi-tone";
import styles from "../dashboard-page.module.css";

function StatCard({ label, value, tone }: { label: string; value: string; tone?: KpiTone }) {
  return (
    <article className={styles.statCard}>
      <span className={styles.statLabel}>
        {tone ? <KpiDot tone={tone} /> : null}
        {label}
      </span>
      <strong className={styles.statValue}>{value}</strong>
    </article>
  );
}

interface KpiCardProps {
  label: string;
  value: number;
  context?: string;
  money?: boolean;
  section: SectionState;
  /** 点击跳转的地址（已带店铺范围）。 */
  to: string;
  tone: KpiTone;
}

/** 指标卡的跳转地址：页面路径 + 页面自己的参数 + 当前店铺范围。 */
export function kpiHref(path: string, shopIds: number[], extra: Record<string, string> = {}): string {
  const params = new URLSearchParams(extra);
  const shops = serializeShopFilter(shopIds);
  if (shops) params.set(SHOP_FILTER_PARAM, shops);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

/** 整张卡可点：悬停底色变浅、名称后出现箭头；链接名就是卡片内容（名称 + 数值）。 */
function KpiLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className={styles.kpiLink}>
      {children}
    </Link>
  );
}

/** 一个指标卡：按数据源各自的加载 / 出错 / 就绪状态显示，出错不影响其他卡片。 */
function KpiCard({ label, value, context, money = false, section, to, tone }: KpiCardProps) {
  if (section.state === "loading") {
    return (
      <div className={styles.placeholderCard}>
        <span className={styles.placeholderLabel}>{label}</span>
        <span className={styles.placeholderSkeleton}>
          <Skeleton label={`正在读取${label}`} lines={1} />
        </span>
      </div>
    );
  }
  if (section.state === "error") {
    return (
      <div className={styles.placeholderCard}>
        <span className={styles.placeholderLabel}>{label}</span>
        <span className={styles.placeholderValue}>暂无</span>
        <Button variant="ghost" size="sm" onClick={section.retry}>
          重试
        </Button>
      </div>
    );
  }
  return (
    <KpiLink to={to}>
      {money ? <StatCard label={label} value={formatCents(value)} tone={tone} /> : <MetricCard label={label} value={value} context={context} tone={tone} />}
    </KpiLink>
  );
}

/** 一组指标卡：灰色组名 + 一行卡片（卡片平分整行）；组内从左到右越来越急。 */
function KpiGroup({ id, title, count, children }: { id: string; title: string; count: number; children: ReactNode }) {
  return (
    <div className={styles.kpiGroup} role="group" aria-labelledby={`kpi-group-${id}`}>
      <div id={`kpi-group-${id}`} className={styles.kpiGroupTitle}>
        {title}
      </div>
      <div className={styles.kpiGrid} data-count={count}>
        {children}
      </div>
    </div>
  );
}

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
    <section aria-label="关键指标" className={styles.kpiGroups}>
      <KpiGroup id="ship" title="发货" count={3}>
        <KpiCard label="待发货" value={kpis.stockUp} section={sections.orderCounts} to={href("/labeling")} tone="info" />
        <KpiCard label="24 小时内须发" value={kpis.expShip} section={sections.orderCounts} to={href("/orders")} tone="warning" />
        <KpiCard label="超时未发" value={kpis.shipDelay} section={sections.orderCounts} to={href("/orders")} tone="danger" />
      </KpiGroup>
      <KpiGroup id="aftersale-stock" title="售后与库存" count={3}>
        <KpiCard label="售后待办" value={kpis.aftersalePending} section={sections.aftersale} to={href("/aftersale")} tone="violet" />
        <KpiCard label="库存预警" value={kpis.alarmCount} section={sections.stock} to={href("/stock", { view: "alarm" })} tone="warning" />
        <KpiCard label="售罄" value={kpis.soldOutCount} section={sections.stock} to={href("/stock")} tone="danger" />
      </KpiGroup>
      <KpiGroup id="shop-fund" title="店铺与资金" count={4}>
        <KpiLink to={href("/shops")}>
          <StatCard
            label="在营店铺"
            value={`${kpis.activeShops} / ${kpis.totalShops}`}
            tone={kpis.activeShops < kpis.totalShops ? "warning" : "success"}
          />
        </KpiLink>
        <KpiCard label="在售商品" value={kpis.onsaleCount} section={sections.products} to={href("/catalog")} tone="success" />
        <KpiCard label="待结算金额" value={kpis.unsettledCents} money section={sections.fund} to={href("/fund")} tone="info" />
        <KpiCard label="保证金余额" value={kpis.marginCents} money section={sections.fund} to={href("/fund", { tab: "margin" })} tone="neutral" />
      </KpiGroup>
    </section>
  );
}

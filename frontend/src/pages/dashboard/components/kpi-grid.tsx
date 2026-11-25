import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { Button } from "@/components/arc/button/button";
import { formatCents } from "@/lib/money-format";
import type { SectionState } from "../hooks/use-dashboard";
import type { DashboardKpis } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

function StatCard({ label, value, context }: { label: string; value: string; context: string }) {
  return (
    <article className={styles.statCard}>
      <span className={styles.statLabel}>{label}</span>
      <strong className={styles.statValue}>{value}</strong>
      <span className={styles.statContext}>{context}</span>
    </article>
  );
}

interface KpiCardProps {
  label: string;
  value: number;
  context: string;
  money?: boolean;
  section: SectionState;
}

/** 一个指标卡：按数据源各自的加载 / 出错 / 就绪状态显示，出错不影响其他卡片。 */
function KpiCard({ label, value, context, money = false, section }: KpiCardProps) {
  if (section.state === "loading") {
    return (
      <div className={styles.placeholderCard}>
        <span className={styles.placeholderLabel}>{label}</span>
        <Skeleton label={`正在读取${label}`} lines={2} />
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
  if (money) return <StatCard label={label} value={formatCents(value)} context={context} />;
  return <MetricCard label={label} value={value} context={context} />;
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
  return (
    <section aria-label="关键指标">
      <div className={styles.kpiGrid}>
        <StatCard
          label="在营店铺"
          value={`${kpis.activeShops} / ${kpis.totalShops}`}
          context="会话有效且未停用"
        />
        <KpiCard label="待发货" value={kpis.stockUp} context="平台口径计数" section={sections.orderCounts} />
        <KpiCard label="24 小时内须发" value={kpis.expShip} context="平台口径计数" section={sections.orderCounts} />
        <KpiCard label="超时未发" value={kpis.shipDelay} context="需要优先处理" section={sections.orderCounts} />
        <KpiCard label="售后待办" value={kpis.aftersalePending} context="待办队列合计" section={sections.aftersale} />
        <KpiCard label="待结算金额" value={kpis.unsettledCents} context="全部店铺待结算合计" money section={sections.fund} />
        <KpiCard label="保证金余额" value={kpis.marginCents} context="已同步的保证金账户" money section={sections.fund} />
        <KpiCard label="库存预警" value={kpis.alarmCount} context="平台标记需补货" section={sections.stock} />
        <KpiCard label="售罄" value={kpis.soldOutCount} context="总库存为 0" section={sections.stock} />
        <KpiCard label="在售商品" value={kpis.onsaleCount} context="平台在售状态" section={sections.products} />
      </div>
    </section>
  );
}

import { MetricCard } from "@/components/arc/metric-card/metric-card";
import metricCard from "@/components/arc/metric-card/metric-card.module.css";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { CountMeta } from "@/components/custom/shop-failure-alert/count-meta";
import { formatCents } from "@/lib/money-format";
import { settledMarginTotal, type FundSummary } from "../logic/fund-page";
import { KpiDot, type KpiTone } from "@/lib/kpi-tone";
import styles from "../fund-page.module.css";

/**
 * 金额卡：MetricCard 只收数字、不能带 ¥ 和两位小数，这里沿用它的样式放格式化好的金额（不可点）。
 */
function AmountCard({ label, cents, tone }: { label: string; cents: number; tone: KpiTone }) {
  return (
    <article className={metricCard.card}>
      <div className={metricCard.top}>
        <span className={metricCard.name}>
          <KpiDot tone={tone} />
          <span className="cell-ellipsis">{label}</span>
        </span>
      </div>
      <strong className={styles.amount}>{formatCents(cents)}</strong>
    </article>
  );
}

/** 多店资金概览：待结算总额 / 待结算单数 / 已同步保证金余额合计。金额一律分 → 展示时换算。 */
export function FundSummaryCards({
  loading,
  error,
  data,
  onRetry,
}: {
  loading: boolean;
  error: boolean;
  data: FundSummary | undefined;
  onRetry: () => void;
}) {
  if (loading) return <Skeleton label="正在读取资金概览" lines={2} />;
  if (error || !data) return <LoadError size="sm" title="读取资金概览失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  const synced = data.shops.filter((shop) => shop.synced_at).length;
  const latest = data.shops
    .map((shop) => shop.synced_at)
    .filter((value): value is string => value !== null)
    .sort()
    .pop();
  return (
    <div className={styles.counts}>
      <div className="count-row">
        <AmountCard label="待结算总额" cents={data.total_unsettled_amount_cents} tone="info" />
        <MetricCard label="待结算订单" value={data.total_unsettled_count} tone="info" />
        <AmountCard label={`保证金余额 · ${synced} 家店`} cents={settledMarginTotal(data)} tone="neutral" />
      </div>
      <CountMeta fetchedAt={latest} />
    </div>
  );
}

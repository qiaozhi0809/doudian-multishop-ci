import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatCents } from "@/lib/money-format";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { settledMarginTotal, type FundSummary } from "../logic/fund-page";
import styles from "../fund-page.module.css";

function StatCard({ label, value, context }: { label: string; value: string; context: string }) {
  return (
    <article className={styles.statCard}>
      <span className={styles.statLabel}>{label}</span>
      <strong className={styles.statValue}>{value}</strong>
      <span className={styles.statContext}>{context}</span>
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
  if (error || !data) {
    return (
      <div className={styles.counts}>
        <Alert tone="danger" title="读取资金概览失败，请确认本地服务正常后重试" />
        <div>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            重新读取
          </Button>
        </div>
      </div>
    );
  }
  const synced = data.shops.filter((shop) => shop.synced_at).length;
  const latest = data.shops
    .map((shop) => shop.synced_at)
    .filter((value): value is string => value !== null)
    .sort()
    .pop();
  return (
    <div className={styles.counts}>
      <div className={styles.countGrid}>
        <StatCard
          label="待结算总额"
          value={formatCents(data.total_unsettled_amount_cents)}
          context="全部店铺待结算合计（平台口径，单位分）"
        />
        <StatCard
          label="待结算订单"
          value={String(data.total_unsettled_count)}
          context="待结算明细条数"
        />
        <StatCard
          label="保证金余额"
          value={formatCents(settledMarginTotal(data))}
          context={`已同步 ${synced} 家店的保证金账户`}
        />
      </div>
      {latest && (
        <div className={styles.countMeta}>
          <span title={formatBjTime(latest)}>数据时间 {formatBjTimeSmart(latest)}</span>
        </div>
      )}
    </div>
  );
}

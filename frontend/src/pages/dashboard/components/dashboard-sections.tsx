import { Alert } from "@/components/arc/alert/alert";
import { Badge } from "@/components/arc/badge/badge";
import type { PendingMetric, SourceFailure } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

/** 部分店铺上游失败：不让整页报错，提示合计不含这些店并列出原因。 */
export function SourceFailures({
  failures,
  shopName,
}: {
  failures: SourceFailure[];
  shopName: (id: number) => string;
}) {
  const unique = [...new Map(failures.map((failure) => [failure.shopId, failure])).values()];
  if (unique.length === 0) return null;
  return (
    <section className={styles.failureBlock}>
      <Alert tone="warning" title={`${unique.length} 家店未取到部分平台数据，合计不含这些店`} />
      <ul className={styles.failList}>
        {unique.map((failure) => (
          <li key={failure.shopId}>
            {shopName(failure.shopId)}：{failure.error ?? "原因未知，请稍后重试"}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** 需要后端补数据才能算的指标：明确标「待补」，不展示估算值。 */
export function PendingMetrics({ items }: { items: PendingMetric[] }) {
  return (
    <section className={styles.pendingCard} aria-label="待补指标">
      <h2 className={styles.sectionTitle}>经营指标（待补）</h2>
      <p className={styles.sectionNote}>
        这些指标需要订单事实表或售后时间字段，接口补齐后在这里展示；当前不显示估算值
      </p>
      <ul className={styles.pendingList}>
        {items.map((item) => (
          <li key={item.label} className={styles.pendingItem}>
            <div className={styles.pendingHead}>
              <span>{item.label}</span>
              <Badge tone="neutral">待补</Badge>
            </div>
            <p className={styles.pendingReason}>{item.reason}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

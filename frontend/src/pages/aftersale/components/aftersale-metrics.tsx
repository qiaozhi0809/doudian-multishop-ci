import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { CountMeta } from "@/components/custom/shop-failure-alert/count-meta";
import { ShopFailureAlert } from "@/components/custom/shop-failure-alert/shop-failure-alert";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { AftersaleQuick, AggregatedAftersaleCounts } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";

interface MetricsProps {
  loading: boolean;
  error: boolean;
  data: AggregatedAftersaleCounts | undefined;
  shopName: (id: number) => string;
  /** 顶部横条里已列出的店：不在未取到提示里重复 */
  bannerShopIds: ReadonlySet<number>;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: AftersaleQuick) => { selected: boolean; onSelect: () => void };
}

/** 平台口径的售后计数：待办 / 待审核 / 临近超时，也是快捷筛选。取不到的店单独列出，不当 0 合计。 */
export function AftersaleMetrics({ loading, error, data, shopName, bannerShopIds, onRetry, cardProps }: MetricsProps) {
  if (loading) return <Skeleton label="正在读取售后计数" lines={SKELETON_LINES.count} />;
  if (error || !data) return <LoadError size="sm" title="读取售后计数失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  return (
    <div className={styles.counts}>
      <ShopFailureAlert failures={data.failures} shopName={shopName} bannerShopIds={bannerShopIds} />
      {data.hasData && (
        <>
          <div className="count-row">
            <MetricCard label="待办售后" value={data.pendingTotal} tone="violet" {...cardProps("pending")} />
            <MetricCard label="待审核" value={data.auditTotal} tone="warning" {...cardProps("audit")} />
            <MetricCard label="临近超时" value={data.approachingDeadline} tone="danger" {...cardProps("due_soon")} />
          </div>
          <CountMeta fetchedAt={data.fetchedAt} partial={data.failedShopIds.length > 0} />
        </>
      )}
    </div>
  );
}

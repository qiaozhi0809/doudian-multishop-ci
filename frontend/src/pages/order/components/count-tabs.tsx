import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { CountMeta } from "@/components/custom/shop-failure-alert/count-meta";
import { ShopFailureAlert } from "@/components/custom/shop-failure-alert/shop-failure-alert";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import { COUNT_ITEMS, type AggregatedCounts, type CountKey } from "../logic/aggregate-counts";
import styles from "../order-page.module.css";

interface CountTabsProps {
  state: "loading" | "error" | "ready";
  data?: AggregatedCounts;
  shopName: (id: number) => string;
  /** 顶部横条里已列出的店：不在未取到提示里重复 */
  bannerShopIds: ReadonlySet<number>;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: CountKey) => { selected: boolean; onSelect: () => void };
}

/** 平台口径的四项计数，也是快捷筛选（点卡片筛下方本地列表）。部分店铺取不到时在合计旁提示，不当 0 合计。 */
export function CountTabs({ state, data, shopName, bannerShopIds, onRetry, cardProps }: CountTabsProps) {
  if (state === "loading") return <Skeleton label="正在读取订单计数" lines={SKELETON_LINES.count} />;
  if (state === "error" || !data) return <LoadError size="sm" title="读取订单计数失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  return (
    <div className={styles.counts}>
      <ShopFailureAlert failures={data.failures} shopName={shopName} bannerShopIds={bannerShopIds} />
      {data.hasData && (
        <>
          <div className="count-row">
            {COUNT_ITEMS.map((item) => (
              <MetricCard key={item.key} label={item.label} value={data.totals[item.key]} tone={item.tone} {...cardProps(item.key)} />
            ))}
          </div>
          <CountMeta fetchedAt={data.fetchedAt} partial={data.failedShopIds.length > 0} />
        </>
      )}
    </div>
  );
}

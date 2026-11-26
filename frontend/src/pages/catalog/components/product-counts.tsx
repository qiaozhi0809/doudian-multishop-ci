import { Alert } from "@/components/arc/alert/alert";
import { Badge } from "@/components/arc/badge/badge";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { CountMeta } from "@/components/custom/shop-failure-alert/count-meta";
import { ShopFailureAlert } from "@/components/custom/shop-failure-alert/shop-failure-alert";
import {
  PRODUCT_COUNT_ITEMS,
  aggregateProductCounts,
  type GroupItem,
  type ProductCountKey,
  type ProductCountsResponse,
} from "../logic/catalog-page";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import styles from "../catalog-page.module.css";

interface CountsProps {
  loading: boolean;
  error: boolean;
  data: ProductCountsResponse | undefined;
  shopName: (id: number) => string;
  /** 顶部横条里已列出的店：不在未取到提示里重复 */
  bannerShopIds: ReadonlySet<number>;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: ProductCountKey) => { selected: boolean; onSelect: () => void };
}

/** 商品状态计数（平台口径），也是快捷筛选（点卡片筛下方本地列表）。 */
export function ProductCounts({ loading, error, data, shopName, bannerShopIds, onRetry, cardProps }: CountsProps) {
  if (loading) return <Skeleton label="正在读取商品计数" lines={SKELETON_LINES.count} />;
  if (error || !data) return <LoadError size="sm" title="读取商品计数失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  const aggregated = aggregateProductCounts(data);
  return (
    <div className={styles.counts}>
      <ShopFailureAlert failures={aggregated.failures} shopName={shopName} bannerShopIds={bannerShopIds} />
      {aggregated.hasData && (
        <>
          <div className="count-row">
            {PRODUCT_COUNT_ITEMS.map((item) => (
              <MetricCard
                key={item.key}
                label={item.label}
                value={aggregated.totals[item.key]}
                tone={item.tone}
                {...cardProps(item.key)}
              />
            ))}
          </div>
          <CountMeta fetchedAt={aggregated.fetchedAt} partial={aggregated.failedShopIds.length > 0} />
        </>
      )}
    </div>
  );
}

/** 商品分组（跨店合并，只做参考展示）。 */
export function ProductGroups({
  loading,
  error,
  groups,
}: {
  loading: boolean;
  error: boolean;
  groups: GroupItem[];
}) {
  // 分组只是参考信息，逐店实时读取：读取中不占位（否则卡片和表格之间留一条灰条，读完常常又没有分组，表格往上跳）
  if (loading) return null;
  if (error) return <Alert tone="warning" title="商品分组读取失败" />;
  if (groups.length === 0) return null;
  return (
    <div className={styles.groupRow}>
      <span className={styles.groupLabel}>商品分组</span>
      {groups.map((group) => (
        <Badge key={group.group_id} tone="neutral" outline>
          {group.name ?? `分组 ${group.group_id}`}
        </Badge>
      ))}
    </div>
  );
}

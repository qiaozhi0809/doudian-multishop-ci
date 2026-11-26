import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import {
  PRODUCT_COUNT_ITEMS,
  aggregateProductCounts,
  type GroupItem,
  type ProductCountKey,
  type ProductCountsResponse,
} from "../logic/catalog-page";
import styles from "../catalog-page.module.css";

interface CountsProps {
  loading: boolean;
  error: boolean;
  data: ProductCountsResponse | undefined;
  shopName: (id: number) => string;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: ProductCountKey) => { selected: boolean; onSelect: () => void };
}

/** 商品状态计数（平台口径），也是快捷筛选（点卡片筛下方本地列表）。 */
export function ProductCounts({ loading, error, data, shopName, onRetry, cardProps }: CountsProps) {
  const [expanded, setExpanded] = useState(false);
  if (loading) return <Skeleton label="正在读取商品计数" lines={2} />;
  if (error || !data) {
    return (
      <div className={styles.counts}>
        <Alert tone="danger" title="读取商品计数失败，请确认本地服务正常后重试" />
        <div>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            重新读取
          </Button>
        </div>
      </div>
    );
  }
  const aggregated = aggregateProductCounts(data);
  return (
    <div className={styles.counts}>
      {aggregated.failedShopIds.length > 0 && (
        <Alert tone="warning" title={`${aggregated.failedShopIds.length} 家店未取到商品计数`}>
          <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
            {expanded ? "收起原因" : "查看原因"}
          </Button>
          {expanded && (
            <ul className={styles.failList}>
              {aggregated.failures.map((f) => (
                <li key={f.shopId}>
                  {shopName(f.shopId)}：{f.error ?? "原因未知，请稍后重试"}
                </li>
              ))}
            </ul>
          )}
        </Alert>
      )}
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
          <div className={styles.countMeta}>
            {aggregated.fetchedAt && (
              <span title={formatBjTime(aggregated.fetchedAt)}>
                数据时间 {formatBjTimeSmart(aggregated.fetchedAt)}
              </span>
            )}
            {aggregated.failedShopIds.length > 0 && <span>合计不含未取到的店铺</span>}
          </div>
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

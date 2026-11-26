import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import type { AftersaleQuick, AggregatedAftersaleCounts } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";

interface MetricsProps {
  loading: boolean;
  error: boolean;
  data: AggregatedAftersaleCounts | undefined;
  shopName: (id: number) => string;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: AftersaleQuick) => { selected: boolean; onSelect: () => void };
}

/** 平台口径的售后计数：待办 / 待审核 / 临近超时，也是快捷筛选。取不到的店单独列出，不当 0 合计。 */
export function AftersaleMetrics({ loading, error, data, shopName, onRetry, cardProps }: MetricsProps) {
  const [expanded, setExpanded] = useState(false);
  if (loading) return <Skeleton label="正在读取售后计数" lines={2} />;
  if (error || !data) {
    return (
      <div className={styles.counts}>
        <Alert tone="danger" title="读取售后计数失败，请确认本地服务正常后重试" />
        <div>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            重新读取
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className={styles.counts}>
      {data.failedShopIds.length > 0 && (
        <Alert tone="warning" title={`${data.failedShopIds.length} 家店未取到售后计数`}>
          <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
            {expanded ? "收起原因" : "查看原因"}
          </Button>
          {expanded && (
            <ul className={styles.failList}>
              {data.failures.map((f) => (
                <li key={f.shopId}>
                  {shopName(f.shopId)}：{f.error ?? "原因未知，请稍后重试"}
                </li>
              ))}
            </ul>
          )}
        </Alert>
      )}
      {data.hasData && (
        <>
          <div className="count-row">
            <MetricCard label="待办售后" value={data.pendingTotal} tone="violet" {...cardProps("pending")} />
            <MetricCard label="待审核" value={data.auditTotal} tone="warning" {...cardProps("audit")} />
            <MetricCard label="临近超时" value={data.approachingDeadline} tone="danger" {...cardProps("due_soon")} />
          </div>
          <div className={styles.countMeta}>
            {data.fetchedAt && (
              <span title={formatBjTime(data.fetchedAt)}>数据时间 {formatBjTimeSmart(data.fetchedAt)}</span>
            )}
            {data.failedShopIds.length > 0 && <span>合计不含未取到的店铺</span>}
          </div>
        </>
      )}
    </div>
  );
}

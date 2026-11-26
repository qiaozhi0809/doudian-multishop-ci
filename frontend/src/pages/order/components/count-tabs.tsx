import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { COUNT_ITEMS, type AggregatedCounts, type CountKey } from "../logic/aggregate-counts";
import styles from "../order-page.module.css";

interface CountTabsProps {
  state: "loading" | "error" | "ready";
  data?: AggregatedCounts;
  shopName: (id: number) => string;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: CountKey) => { selected: boolean; onSelect: () => void };
}

/** 平台口径的四项计数，也是快捷筛选（点卡片筛下方本地列表）。部分店铺取不到时在合计旁提示，不当 0 合计。 */
export function CountTabs({ state, data, shopName, onRetry, cardProps }: CountTabsProps) {
  const [expanded, setExpanded] = useState(false);
  if (state === "loading") return <Skeleton label="正在读取订单计数" lines={2} />;
  if (state === "error" || !data) {
    return (
      <div className={styles.counts}>
        <Alert tone="danger" title="读取订单计数失败，请确认本地服务正常后重试" />
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
        <Alert tone="warning" title={`${data.failedShopIds.length} 家店未取到`}>
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
            {COUNT_ITEMS.map((item) => (
              <MetricCard key={item.key} label={item.label} value={data.totals[item.key]} tone={item.tone} {...cardProps(item.key)} />
            ))}
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

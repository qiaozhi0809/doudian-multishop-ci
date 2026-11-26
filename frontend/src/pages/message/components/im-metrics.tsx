import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { Counts, ImQuick } from "../logic/message-page";

interface ImMetricsProps {
  data: Counts | undefined;
  loading: boolean;
  onRetry: () => void;
  /** 快捷筛选：点卡片筛下方列表，再点清除。 */
  cardProps: (key: ImQuick) => { selected: boolean; onSelect: () => void };
}

export function ImMetrics({ data, loading, onRetry, cardProps }: ImMetricsProps) {
  if (loading) return <Skeleton label="正在读取会话计数" lines={SKELETON_LINES.count} />;
  if (!data) return <LoadError size="sm" title="读取会话计数失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  return (
    <div className="count-row">
      <MetricCard label="未读会话" value={data.unread} tone="info" {...cardProps("unread")} />
      <MetricCard label="待回复" value={data.waiting} tone="warning" {...cardProps("waiting")} />
      <MetricCard label="超 3 分钟未回复" value={data.overdue} tone="danger" {...cardProps("overdue")} />
      <MetricCard label="今日会话" value={data.today} tone="neutral" {...cardProps("today")} />
    </div>
  );
}

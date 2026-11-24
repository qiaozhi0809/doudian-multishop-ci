import { Link } from "react-router-dom";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/arc/popover/popover";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { AttentionRow, HealthSummary } from "../logic/health-summary";
import styles from "../app-shell.module.css";

interface HealthIndicatorProps {
  state: "loading" | "error" | "ready";
  summary: HealthSummary;
  attention: AttentionRow[];
  onRetry: () => void;
}

function label(summary: HealthSummary): string {
  if (summary.level === "error") return `${summary.needsLogin} 家需重新登录`;
  if (summary.level === "warn") return `${summary.expiring} 家即将过期`;
  return "会话正常";
}

const TONE = { ok: "success", warn: "warning", error: "danger" } as const;

/** 会话健康指示：正常时只是一个状态标记；有店铺需要处理时可点开查看并前往店铺页。 */
export function HealthIndicator({ state, summary, attention, onRetry }: HealthIndicatorProps) {
  if (state === "loading") {
    return (
      <div className={styles.healthSkeleton}>
        <Skeleton label="正在读取会话状态" lines={1} />
      </div>
    );
  }
  if (state === "error") {
    return (
      <Button variant="ghost" size="sm" onClick={onRetry}>
        重新读取店铺
      </Button>
    );
  }
  const text = label(summary);
  const badge = (
    <Badge tone={TONE[summary.level]} dot>
      {text}
    </Badge>
  );
  if (summary.level === "ok") return badge;

  return (
    <Popover>
      <PopoverTrigger aria-label={text} style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }}>
        {badge}
      </PopoverTrigger>
      <PopoverContent align="end" className={styles.attentionPanel}>
        <ul className={styles.attentionList}>
          {attention.map((row) => (
            <li key={row.id} className={styles.attentionRow}>
              <span>{row.name}</span>
              <Badge tone={row.kind === "needs_login" ? "danger" : "warning"}>
                {row.kind === "needs_login" ? "需重新登录" : "即将过期"}
              </Badge>
            </li>
          ))}
        </ul>
        <Link to="/shops" className={styles.attentionLink}>
          前往店铺页
        </Link>
      </PopoverContent>
    </Popover>
  );
}

import { Link } from "react-router-dom";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/arc/popover/popover";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { AttentionRow, HealthSummary } from "../logic/health-summary";
import styles from "../app-shell.module.css";

export interface QuickLoginState {
  pendingIds: number[];
  waitingIds: number[];
  errors: Record<number, string>;
  onLogin: (id: number) => void;
}

interface HealthIndicatorProps {
  state: "loading" | "error" | "ready";
  summary: HealthSummary;
  attention: AttentionRow[];
  onRetry: () => void;
  login: QuickLoginState;
}

function label(summary: HealthSummary): string {
  if (summary.level === "error") return `${summary.errorCount} 家店需处理`;
  if (summary.level === "warn") return `${summary.warnCount} 家店即将到期`;
  if (summary.level === "empty") return "还没有店铺";
  return "店铺正常";
}

const TONE = { empty: "neutral", ok: "success", warn: "warning", error: "danger" } as const;

/** 店铺状态指示：掉线 / 会话过期为红点，点开可查看原因并一键重新扫码登录。 */
export function HealthIndicator({ state, summary, attention, onRetry, login }: HealthIndicatorProps) {
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
  if (summary.level === "empty") {
    return (
      <Link to="/shops" className={styles.badgeLink}>
        {badge}
      </Link>
    );
  }

  return (
    <Popover>
      <PopoverTrigger aria-label={text} className={styles.popoverTrigger}>
        {badge}
      </PopoverTrigger>
      <PopoverContent align="end" className={styles.attentionPanel}>
        <ul className={styles.attentionList}>
          {attention.map((row) => {
            const waiting = login.waitingIds.includes(row.id);
            const pending = login.pendingIds.includes(row.id);
            return (
              <li key={row.id} className={styles.attentionItem}>
                <div className={styles.attentionRow}>
                  <span>{row.name}</span>
                  <Badge tone={row.tone}>{row.label}</Badge>
                </div>
                {row.action === "login" &&
                  (waiting ? (
                    <Badge tone="warning">等待扫码</Badge>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={pending}
                      onClick={() => login.onLogin(row.id)}
                    >
                      重新登录
                    </Button>
                  ))}
                {login.errors[row.id] && (
                  <p className={styles.attentionError}>{login.errors[row.id]}</p>
                )}
              </li>
            );
          })}
        </ul>
        <Link to="/shops" className={styles.attentionLink}>
          前往店铺页
        </Link>
      </PopoverContent>
    </Popover>
  );
}

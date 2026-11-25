import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { DropdownMenu } from "@/components/arc/dropdown-menu/dropdown-menu";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { formatBjTime, formatRemaining } from "@/lib/time-format";
import type { ShopRow } from "@/lib/use-shops";
import {
  egressBadge,
  egressModeLabel,
  pausedBadge,
  primaryAction,
  readyBadge,
  scanDisabledReason,
  shopStatusBadge,
  type Tone,
} from "../logic/shop-status";
import styles from "../shop-page.module.css";

const badgeTone = (tone: Tone) => tone;

export function StatusCell({ row, waiting, onResume }: { row: ShopRow; waiting: boolean; onResume: () => void }) {
  const status = shopStatusBadge(row);
  const paused = pausedBadge(row);
  return (
    <div className={styles.cellStack}>
      <div className={styles.cellRow}>
        <Badge tone={badgeTone(status.tone)} dot>
          {status.label}
        </Badge>
        {waiting && <Badge tone="info">等待扫码</Badge>}
      </div>
      {paused && (
        <div className={styles.cellRow}>
          <Tooltip content={`原因：${paused.reason}`}>
            <span className={styles.tip} tabIndex={0}>
              <Badge tone="danger" dot>
                {paused.label}
              </Badge>
            </span>
          </Tooltip>
          <Button variant="secondary" size="sm" onClick={onResume}>
            恢复
          </Button>
        </div>
      )}
    </div>
  );
}

export function EgressCell({ row }: { row: ShopRow }) {
  const egress = egressBadge(row);
  return (
    <div className={styles.cellStack}>
      <span>
        {egressModeLabel(row)}
        {row.proxy_display ? <span className={styles.muted}>{` ${row.proxy_display}`}</span> : null}
      </span>
      <Badge tone={badgeTone(egress.tone)} dot>
        {egress.label}
      </Badge>
    </div>
  );
}

export function ExpiryCell({ row }: { row: ShopRow }) {
  return (
    <div className={styles.cellStack}>
      <span className={styles.tabular}>{formatBjTime(row.expires_at)}</span>
      {row.expires_at && <span className={styles.muted}>{formatRemaining(row.expires_at)}</span>}
    </div>
  );
}

export function ReadyCell({ row }: { row: ShopRow }) {
  const ready = readyBadge(row);
  const badge = <Badge tone={badgeTone(ready.tone)}>{ready.label}</Badge>;
  if (!ready.detail) return badge;
  return (
    <Tooltip content={ready.detail}>
      <span className={styles.tip} tabIndex={0}>
        {badge}
      </span>
    </Tooltip>
  );
}

export interface RowActions {
  onLogin: () => void;
  onEgress: () => void;
  onCheckEgress: () => void;
  onProbe: () => void;
  onSyncBase: () => void;
  onViewBase: () => void;
}

interface ActionsCellProps {
  row: ShopRow;
  actions: RowActions;
  pending: string[];
  waiting: boolean;
}

/** 操作列：按引导顺序在行内直接显示一个主操作（设置出口 → 检查出口 → 扫码登录），其余收进「更多」。 */
export function ActionsCell({ row, actions, pending, waiting }: ActionsCellProps) {
  const busy = (action: string) => pending.includes(`${action}:${row.id}`);
  const primary = primaryAction(row);
  const reason = scanDisabledReason(row);
  const scan = (
    <Button variant="secondary" size="sm" disabled={reason !== null || waiting} loading={busy("login")} onClick={actions.onLogin}>
      扫码登录
    </Button>
  );

  return (
    <div className={styles.actions}>
      {primary === "set-egress" && (
        <Button variant="secondary" size="sm" onClick={actions.onEgress}>
          设置出口
        </Button>
      )}
      {primary === "check-egress" && (
        <Button variant="secondary" size="sm" loading={busy("egress-check")} onClick={actions.onCheckEgress}>
          检查出口
        </Button>
      )}
      {primary === "login" &&
        (reason ? (
          <Tooltip content={reason}>
            <span className={styles.tip} tabIndex={0}>
              {scan}
            </span>
          </Tooltip>
        ) : (
          scan
        ))}
      {primary !== "set-egress" && (
        <Button variant="ghost" size="sm" onClick={actions.onEgress}>
          设置出口
        </Button>
      )}
      <DropdownMenu
        label="更多"
        items={[
          ...(primary === "check-egress" || row.egress_mode === null
            ? []
            : [{ label: "检查出口", onSelect: actions.onCheckEgress, disabled: busy("egress-check") }]),
          { label: "探测会话", onSelect: actions.onProbe, disabled: busy("probe") },
          { label: "同步基础数据", onSelect: actions.onSyncBase, disabled: busy("sync-base") },
          { label: "查看基础数据", onSelect: actions.onViewBase, separatorBefore: true },
        ]}
      />
    </div>
  );
}

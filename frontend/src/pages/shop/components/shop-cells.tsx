import { useCallback } from "react";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { RowMenu } from "@/components/custom/row-menu/row-menu";
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
} from "../logic/shop-status";
import styles from "../shop-page.module.css";

/** 店铺名单元格；highlighted 时把所在行标为当前（`aria-current`，带底色）并滚动到视野中间。 */
export function NameCell({ name, highlighted }: { name: string; highlighted: boolean }) {
  const mark = useCallback((el: HTMLSpanElement | null) => {
    const row = el?.closest("tr");
    if (!row) return;
    row.setAttribute("aria-current", "true");
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    return () => row.removeAttribute("aria-current");
  }, []);
  return (
    <span className={styles.shopName} ref={highlighted ? mark : undefined}>
      {name}
    </span>
  );
}

export function StatusCell({ row, waiting, onResume }: { row: ShopRow; waiting: boolean; onResume: () => void }) {
  const status = shopStatusBadge(row);
  const paused = pausedBadge(row);
  if (!paused) {
    return (
      <div className={styles.cellLine}>
        <Badge tone={status.tone} dot>
          {status.label}
        </Badge>
        {waiting && <Badge tone="info">等待扫码</Badge>}
      </div>
    );
  }
  // 风控暂停是少见的例外：多一行放「风控暂停」和「恢复」
  return (
    <div className={styles.cellStack}>
      <div className={styles.cellRow}>
        <Badge tone={status.tone} dot>
          {status.label}
        </Badge>
        {waiting && <Badge tone="info">等待扫码</Badge>}
      </div>
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
    </div>
  );
}

/** 一行：出口方式（代理时带代理地址，悬停看全）+ 出口状态。 */
export function EgressCell({ row }: { row: ShopRow }) {
  const egress = egressBadge(row);
  const mode = egressModeLabel(row);
  return (
    <div className={styles.cellLine}>
      <span className={styles.egressMode} title={row.proxy_display ? `${mode} ${row.proxy_display}` : undefined}>
        {mode}
        {row.proxy_display ? <span className={styles.muted}>{` ${row.proxy_display}`}</span> : null}
      </span>
      <Badge tone={egress.tone} dot>
        {egress.label}
      </Badge>
    </div>
  );
}

/** 一行：只显示剩余天数（运营要看的是还剩多久）；具体到期时间放在悬停提示里。 */
export function ExpiryCell({ row }: { row: ShopRow }) {
  if (!row.expires_at) return <span className={styles.tabular}>{formatBjTime(null)}</span>;
  return (
    <span className={styles.tabular} title={`到期时间 ${formatBjTime(row.expires_at)}`}>
      {formatRemaining(row.expires_at)}
    </span>
  );
}

export function ReadyCell({ row }: { row: ShopRow }) {
  const ready = readyBadge(row);
  const badge = <Badge tone={ready.tone}>{ready.label}</Badge>;
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
  onEdit: () => void;
  onToggle: () => void;
}

interface ActionsCellProps {
  row: ShopRow;
  actions: RowActions;
  pending: string[];
  waiting: boolean;
}

/** 操作列：按引导顺序在行内只露一个主操作（设置出口 → 检查出口 → 扫码登录），其余收进「⋯」。 */
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
      <RowMenu
        items={[
          ...(primary === "set-egress" ? [] : [{ label: "设置出口", onSelect: actions.onEgress }]),
          ...(primary === "check-egress" || row.egress_mode === null
            ? []
            : [{ label: "检查出口", onSelect: actions.onCheckEgress, disabled: busy("egress-check") }]),
          { label: "检查登录状态", onSelect: actions.onProbe, disabled: busy("probe") },
          { label: "更新发货资料", onSelect: actions.onSyncBase, disabled: busy("sync-base") },
          { label: "店铺资料", onSelect: actions.onViewBase, separatorBefore: true },
          { label: "编辑店铺", onSelect: actions.onEdit },
          { label: row.status === "disabled" ? "启用店铺" : "停用店铺", onSelect: actions.onToggle, disabled: busy("toggle") },
        ]}
      />
    </div>
  );
}

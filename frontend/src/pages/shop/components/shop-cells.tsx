import { useCallback, useEffect, useRef } from "react";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { RowMenu } from "@/components/custom/row-menu/row-menu";
import { orEmpty } from "@/lib/empty-text";
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
import { ReasonTip } from "./reason-tip";

/**
 * 店铺名单元格；highlighted 时把所在行标为当前（`aria-current`，带底色），
 * onMark 返回 true（这次高亮还没滚过）时滚动到视野中间。
 */
export function NameCell({ name, highlighted, onMark }: { name: string; highlighted: boolean; onMark: () => boolean }) {
  const latest = useRef(onMark);
  useEffect(() => {
    latest.current = onMark;
  });
  const mark = useCallback((el: HTMLSpanElement | null) => {
    const row = el?.closest("tr");
    if (!row) return;
    row.setAttribute("aria-current", "true");
    if (latest.current()) row.scrollIntoView({ block: "center", behavior: "smooth" });
    return () => row.removeAttribute("aria-current");
  }, []);
  return (
    <span className={`cell-ellipsis ${styles.shopName}`} title={name} ref={highlighted ? mark : undefined}>
      {name}
    </span>
  );
}

/** 单行文本：列窄时省略，悬停看全；空值显示「暂无」。 */
export function TextCell({ value }: { value: string | null }) {
  return (
    <span className="cell-ellipsis" title={value ?? undefined}>
      {orEmpty(value)}
    </span>
  );
}

/** 一行：会话状态、等待扫码、风控暂停（原因悬停看）；恢复按钮在操作列。 */
export function StatusCell({ row, waiting }: { row: ShopRow; waiting: boolean }) {
  const status = shopStatusBadge(row);
  const paused = pausedBadge(row);
  return (
    <div className={`${styles.cellLine} ${styles.cellClip}`}>
      <Badge tone={status.tone} dot>
        {status.label}
      </Badge>
      {waiting && (
        <Badge tone="info" dot>
          等待扫码
        </Badge>
      )}
      {paused && (
        <ReasonTip reason={`原因：${paused.reason}`}>
          <Badge tone="danger" dot>
            {paused.label}
          </Badge>
        </ReasonTip>
      )}
    </div>
  );
}

/** 一行：出口方式（代理地址放不下时省略，悬停看全）+ 出口状态（悬停看全）。 */
export function EgressCell({ row }: { row: ShopRow }) {
  const egress = egressBadge(row);
  const mode = egressModeLabel(row);
  return (
    <div className={`${styles.cellLine} ${styles.cellClip}`}>
      <span className={styles.egressMode} title={row.proxy_display ? `${mode} ${row.proxy_display}` : undefined}>
        <span>{mode}</span>
        {row.proxy_display ? <span className={styles.egressAddress}>{row.proxy_display}</span> : null}
      </span>
      <Badge tone={egress.tone} dot title={egress.label}>
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
  return (
    <ReasonTip reason={ready.detail}>
      <Badge tone={ready.tone} dot>
        {ready.label}
      </Badge>
    </ReasonTip>
  );
}

export interface RowActions {
  onLogin: () => void;
  onResume: () => void;
  onEgress: () => void;
  onCheckEgress: () => void;
  onProbe: () => void;
  onSyncBase: () => void;
  onViewBase: () => void;
  onEdit: () => void;
  onToggleIm: () => void;
  onToggle: () => void;
}

interface ActionsCellProps {
  row: ShopRow;
  actions: RowActions;
  pending: string[];
  waiting: boolean;
}

/** 操作列：行内只露一个主操作（恢复 / 设置出口 → 检查出口 → 扫码登录），其余收进「⋯」。 */
export function ActionsCell({ row, actions, pending, waiting }: ActionsCellProps) {
  const busy = (action: string) => pending.includes(`${action}:${row.id}`);
  const primary = primaryAction(row);
  const reason = scanDisabledReason(row);

  return (
    <div className={styles.actions}>
      {primary === "resume" && (
        <Button variant="secondary" size="sm" loading={busy("resume")} onClick={actions.onResume}>
          恢复
        </Button>
      )}
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
      {primary === "login" && (
        <ReasonTip reason={reason}>
          <Button variant="secondary" size="sm" disabled={reason !== null || waiting} loading={busy("login")} onClick={actions.onLogin}>
            扫码登录
          </Button>
        </ReasonTip>
      )}
      <RowMenu
        items={[
          ...(primary === "set-egress" ? [] : [{ label: "设置出口", onSelect: actions.onEgress }]),
          ...(primary === "check-egress" || row.egress_mode === null
            ? []
            : [{ label: "检查出口", onSelect: actions.onCheckEgress, disabled: busy("egress-check") }]),
          { label: "检查登录状态", onSelect: actions.onProbe, disabled: busy("probe") },
          { label: "更新发货资料", onSelect: actions.onSyncBase, disabled: busy("sync-base") },
          { label: "查看店铺资料", onSelect: actions.onViewBase, separatorBefore: true },
          { label: "编辑店铺", onSelect: actions.onEdit },
          { label: row.im_enabled ? "关闭飞鸽消息" : "开启飞鸽消息", onSelect: actions.onToggleIm, disabled: busy("im") },
          { label: row.status === "disabled" ? "启用店铺" : "停用店铺", onSelect: actions.onToggle, disabled: busy("toggle") },
        ]}
      />
    </div>
  );
}

import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { Switch } from "@/components/arc/switch/switch";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { countsText, type ProgressItem } from "../logic/progress";
import { groupForPanel, lastPage, levelTone, openRows, type NotificationItem, type StrongOpenShop } from "../logic/notification-view";
import styles from "../notification-center.module.css";
import { ProblemLinks } from "./problem-links";

export interface PanelProps {
  progress: ProgressItem[];
  items: NotificationItem[];
  /** 全部未解决的强提醒（来自摘要，与顶部横条一致） */
  strongOpen: StrongOpenShop[];
  total: number;
  pageSize: number;
  page: number;
  onPageChange: (page: number) => void;
  unread: number;
  unreadOnly: boolean;
  onUnreadOnlyChange: (value: boolean) => void;
  muted: boolean;
  onMutedChange: (muted: boolean) => void;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  onOpenItem: (item: NotificationItem) => void;
  onNavigate: (link: string) => void;
  onMarkAllRead: () => void;
}

const FILTERS = [
  { value: "all", label: "全部" },
  { value: "unread", label: "未读" },
];

/** 没有未读时按钮禁用，悬停或聚焦说明原因。 */
function MarkAllRead({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  const button = (
    <Button variant="ghost" disabled={disabled} onClick={onClick}>
      全部已读
    </Button>
  );
  if (!disabled) return button;
  return (
    <Tooltip content="没有未读通知">
      <span tabIndex={0} className={styles.disabledWrap}>
        {button}
      </span>
    </Tooltip>
  );
}

function ItemList({ items, onOpenItem }: { items: NotificationItem[]; onOpenItem: (item: NotificationItem) => void }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            className={styles.item}
            data-unread={item.read_at === null || undefined}
            onClick={() => onOpenItem(item)}
          >
            <span className={styles.dot} data-tone={levelTone(item.level)} aria-hidden="true" />
            <span className={styles.itemTitle}>{item.body ? `${item.title}，${item.body}` : item.title}</span>
            <time className={styles.time} dateTime={item.updated_at} title={formatBjTime(item.updated_at)}>
              {formatBjTimeSmart(item.updated_at)}
            </time>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** 通知面板：进行中 → 待处理（全部未解决的强提醒，一店一行）→ 最近的通知（全部 / 未读、全部已读、分页）。 */
export function Panel(props: PanelProps) {
  const open = openRows(props.strongOpen);
  // 未解决的状态类已在「待处理」里，最近列表不再重复
  const { recent } = groupForPanel(props.items);
  const pages = lastPage(props.total, props.pageSize);
  return (
    <div className={styles.panelBody}>
      <div className={styles.head}>
        <h2 className={styles.heading}>通知</h2>
        <Switch label="提示音" checked={!props.muted} onCheckedChange={(on) => props.onMutedChange(!on)} />
      </div>
      {props.progress.length > 0 && (
        <section className={styles.section} aria-labelledby="notify-progress">
          <h3 id="notify-progress" className={styles.sectionTitle}>进行中</h3>
          <ul className={styles.list}>
            {props.progress.map((task) => (
              <li key={task.id} className={styles.progressRow}>
                <span>{task.title}</span>
                <span className={styles.progressCounts}>{countsText(task)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {open.length > 0 && (
        <section className={styles.section} aria-labelledby="notify-open">
          <h3 id="notify-open" className={styles.sectionTitle}>待处理</h3>
          <ul className={styles.list}>
            {open.map((row) => (
              <li key={row.shopId}>
                <div role="group" aria-label={row.shopName} className={styles.item} data-unread data-static>
                  <span className={styles.dot} data-tone="danger" aria-hidden="true" />
                  <ProblemLinks row={row} onNavigate={props.onNavigate} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className={styles.section} aria-labelledby="notify-recent">
        <h3 id="notify-recent" className={styles.sectionTitle}>最近</h3>
        <div className={styles.listToolbar}>
          <SegmentedControl
            label="通知筛选"
            options={FILTERS}
            value={props.unreadOnly ? "unread" : "all"}
            onValueChange={(value) => props.onUnreadOnlyChange(value === "unread")}
          />
          <MarkAllRead disabled={props.unread === 0} onClick={props.onMarkAllRead} />
        </div>
        {props.loading ? (
          <Skeleton label="正在读取通知" lines={3} />
        ) : props.error ? (
          <div className={styles.error}>
            <Alert tone="danger" title="读取通知失败" />
            <Button variant="secondary" size="sm" onClick={props.onRetry}>
              重新读取
            </Button>
          </div>
        ) : recent.length === 0 ? (
          <p className={styles.empty}>暂无通知</p>
        ) : (
          <ItemList items={recent} onOpenItem={props.onOpenItem} />
        )}
      </section>
      {pages > 1 && (
        <div className={styles.foot}>
          <Pagination page={props.page} pageCount={pages} onPageChange={props.onPageChange} label="通知分页" />
        </div>
      )}
    </div>
  );
}

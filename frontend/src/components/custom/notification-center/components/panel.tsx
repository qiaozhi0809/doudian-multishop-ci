import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Checkbox } from "@/components/arc/checkbox/checkbox";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { countsText, type ProgressItem } from "../logic/progress";
import { groupForPanel, lastPage, levelTone, type NotificationItem } from "../logic/notification-view";
import styles from "../notification-center.module.css";

export interface PanelProps {
  progress: ProgressItem[];
  items: NotificationItem[];
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
  onMarkAllRead: () => void;
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

/** 通知面板：进行中 → 待处理（未解决的状态类）→ 最近的通知 → 全部已读。 */
export function Panel(props: PanelProps) {
  const { open, recent } = groupForPanel(props.items);
  const pages = lastPage(props.total, props.pageSize);
  return (
    <div className={styles.panelBody}>
      <div className={styles.head}>
        <h2 className={styles.heading}>通知</h2>
        <div className={styles.toggles}>
          <Checkbox label="只看未读" checked={props.unreadOnly} onCheckedChange={(v) => props.onUnreadOnlyChange(v === true)} />
          <Checkbox label="提示音" checked={!props.muted} onCheckedChange={(v) => props.onMutedChange(v !== true)} />
        </div>
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
          <ItemList items={open} onOpenItem={props.onOpenItem} />
        </section>
      )}
      <section className={styles.section} aria-labelledby="notify-recent">
        <h3 id="notify-recent" className={styles.sectionTitle}>最近</h3>
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
      <div className={styles.foot}>
        {pages > 1 ? <Pagination page={props.page} pageCount={pages} onPageChange={props.onPageChange} label="通知分页" /> : <span />}
        <Button variant="ghost" size="sm" disabled={props.unread === 0} onClick={props.onMarkAllRead}>
          全部已读
        </Button>
      </div>
    </div>
  );
}

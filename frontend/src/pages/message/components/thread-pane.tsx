import { useEffect, useRef } from "react";
import { MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { ThreadState } from "../hooks/use-thread";
import { formatWait, isOverdue, ordersLink, waitSecondsAt } from "../logic/message-page";
import styles from "../message-page.module.css";
import { MessageLine } from "./message-line";

/** 消息记录：新消息到达或换会话时滚到最新一条。 */
function Messages({ thread }: { thread: ThreadState }) {
  const { data, isLoading, refetch } = thread.messages;
  const box = useRef<HTMLDivElement>(null);
  const newest = data?.items.at(-1)?.message_id;
  useEffect(() => {
    const node = box.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [data?.shop_id, data?.conversation_id, newest]);

  const preview = thread.known?.preview;
  return (
    <div className={styles.messages} ref={box}>
      {isLoading && <Skeleton label="正在读取消息" lines={5} />}
      {thread.loadError && (
        <div className={styles.stack}>
          <Alert tone="danger" title={`读取消息失败：${thread.loadError}`} />
          <div>
            <Button variant="secondary" size="sm" onClick={() => void refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && data.items.length === 0 && !preview && <p className="panel-empty">暂无消息</p>}
      {data && (data.items.length > 0 || preview) && (
        <ol className={styles.lines} aria-label="消息记录">
          {data.items.length > 0 ? (
            data.items.map((m) => <MessageLine key={m.message_id} role={m.sender_role} text={m.text} sentAt={m.sent_at} />)
          ) : (
            <MessageLine role="preview" text={preview!} sentAt={thread.known?.last_at ?? null} />
          )}
        </ol>
      )}
    </div>
  );
}

/** 右栏：只读会话详情。回复在飞鸽里做，这里没有输入框。 */
export function ThreadPane({ thread, shopName, now }: { thread: ThreadState; shopName: string | undefined; now: Date }) {
  const { selection, row, known } = thread;
  if (!selection) {
    return (
      <section className={styles.thread} aria-label="会话详情">
        <div className={styles.threadEmpty}>
          <EmptyState icon={<MessageSquare size={24} strokeWidth={1.75} aria-hidden="true" />} title="选择一个会话" />
        </div>
      </section>
    );
  }
  const waited = waitSecondsAt(row?.waiting_since ?? null, now);
  const shop = known?.shop_name ?? shopName;
  return (
    <section className={styles.thread} aria-label="会话详情">
      <header className={styles.threadHead}>
        <h2 className="section-title">{known?.buyer ?? "买家"}</h2>
        {shop && <span className={styles.shop}>{shop}</span>}
        {waited !== null && (
          <span className={styles.wait} data-overdue={isOverdue(waited) || undefined}>{`等待 ${formatWait(waited)}`}</span>
        )}
      </header>
      <Messages thread={thread} />
      <footer className={styles.actions}>
        <Button loading={thread.opening} onClick={thread.openInFlybird}>
          在飞鸽中回复
        </Button>
        <Link className={styles.linkButton} to={ordersLink(selection.shopId)}>
          查看订单
        </Link>
      </footer>
    </section>
  );
}

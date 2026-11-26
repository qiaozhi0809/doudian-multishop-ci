import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { ThreadState } from "../hooks/use-thread";
import { formatWait, isOverdue, ordersLink, waitSecondsAt } from "../logic/message-page";
import styles from "../message-page.module.css";
import { avatarText } from "./conversation-row";
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
      {isLoading && <Skeleton label="正在读取消息" lines={SKELETON_LINES.list} />}
      {thread.loadError && (
        <LoadError size="sm" title={`读取消息失败：${thread.loadError}`} onRetry={() => void refetch()} />
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
  const navigate = useNavigate();
  if (!selection) {
    return (
      <section className={styles.thread} aria-label="会话详情">
        <div className={styles.threadEmpty}>
          <p className="panel-empty">选择一个会话</p>
        </div>
      </section>
    );
  }
  const waited = waitSecondsAt(row?.waiting_since ?? null, now);
  const shop = known?.shop_name ?? shopName;
  return (
    <section className={styles.thread} aria-label="会话详情">
      <header className={styles.threadHead}>
        <span className={styles.avatar} aria-hidden="true">{avatarText(known?.buyer ?? "买家")}</span>
        <span className={styles.threadTitle}>
          <h2 className="section-title">{known?.buyer ?? "买家"}</h2>
          {shop && <span className={styles.shopTag}>{shop}</span>}
        </span>
        {waited !== null && (
          <span className={styles.waitChip} data-overdue={isOverdue(waited) || undefined}>{`等待 ${formatWait(waited)}`}</span>
        )}
      </header>
      <Messages thread={thread} />
      <footer className={styles.actions}>
        <Button loading={thread.opening} onClick={thread.openInFlybird}>
          在飞鸽中回复
        </Button>
        <Button variant="secondary" onClick={() => void navigate(ordersLink(selection.shopId))}>
          查看订单
        </Button>
      </footer>
    </section>
  );
}

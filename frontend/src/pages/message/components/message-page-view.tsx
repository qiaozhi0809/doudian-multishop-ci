import { NoticeList } from "@/components/custom/notice/notice-list";
import type { MessagePageState } from "../hooks/use-message-page";
import type { ThreadState } from "../hooks/use-thread";
import styles from "../message-page.module.css";
import { ConversationList } from "./conversation-list";
import { ImMetrics } from "./im-metrics";
import { ImStatusStrip } from "./im-status-strip";
import { ThreadPane } from "./thread-pane";

/** 消息页：计数卡 → 接收状态 → 左会话列表、右会话详情。 */
export function MessagePageView({ page, thread }: { page: MessagePageState; thread: ThreadState }) {
  const shopName = page.status.data?.find((s) => s.shop_id === page.selection?.shopId)?.shop_name;
  return (
    <div className={styles.page}>
      <NoticeList notices={page.restart.notices} onDismiss={page.restart.dismissNotice} />
      <NoticeList notices={thread.notices} onDismiss={thread.dismissNotice} />
      <ImMetrics
        data={page.counts.data}
        loading={page.counts.isLoading}
        onRetry={() => void page.counts.refetch()}
        cardProps={page.quick.cardProps}
      />
      <ImStatusStrip
        shops={page.stopped}
        failed={page.status.isError && !page.status.data}
        onRetry={() => void page.status.refetch()}
        pending={page.restart.pending}
        onRestart={page.restart.restart}
      />
      <div className={styles.columns}>
        <ConversationList page={page} />
        <ThreadPane thread={thread} shopName={shopName} now={page.now} />
      </div>
    </div>
  );
}

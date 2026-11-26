import { Badge } from "@/components/arc/badge/badge";
import { formatWait, isOverdue, waitSecondsAt, type Conversation } from "../logic/message-page";
import styles from "../message-page.module.css";

interface ConversationRowProps {
  conversation: Conversation;
  now: Date;
  selected: boolean;
  onSelect: () => void;
}

export function ConversationRow({ conversation, now, selected, onSelect }: ConversationRowProps) {
  const waited = waitSecondsAt(conversation.waiting_since, now);
  return (
    <button
      type="button"
      className={styles.row}
      aria-current={selected || undefined}
      data-overdue={isOverdue(waited) || undefined}
      onClick={onSelect}
    >
      <span className={styles.rowLine}>
        <span className={styles.buyer}>{conversation.buyer}</span>
        <span className={styles.shop}>{conversation.shop_name}</span>
        {waited !== null && <span className={styles.wait}>{`等待 ${formatWait(waited)}`}</span>}
      </span>{" "}
      <span className={styles.rowLine}>
        <span className={styles.preview}>{conversation.preview}</span>
        {conversation.unread > 0 && (
          <Badge tone="info" size="sm" pill title={`未读 ${conversation.unread} 条`}>
            {conversation.unread}
          </Badge>
        )}
      </span>
    </button>
  );
}

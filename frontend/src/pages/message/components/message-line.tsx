import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import { senderLabel, type Message } from "../logic/message-page";
import styles from "../message-page.module.css";

interface LineProps {
  /** 发送方；没有采集到消息、只显示最新预览时为 preview。 */
  role: Message["sender_role"] | "preview";
  text: string;
  sentAt: string | null;
}

export function MessageLine({ role, text, sentAt }: LineProps) {
  return (
    <li className={styles.message} data-role={role}>
      <span className={styles.meta}>
        <span>{role === "preview" ? "最新消息" : senderLabel(role)}</span>
        {sentAt && (
          <time dateTime={sentAt} title={formatBjTime(sentAt)}>
            {formatBjTimeSmart(sentAt)}
          </time>
        )}
      </span>
      <span className={styles.text}>{text}</span>
    </li>
  );
}

import { useEffect } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { useNotice } from "./notice";
import styles from "./notice.module.css";
import type { QueuedNotice } from "./use-notice-queue";

/**
 * 操作结果与等待态：在外壳里交给右下角浮动提示（同 key 只留一条）；
 * 单独渲染页面（没有 NoticeProvider，如页面测试）时退回页面内提示条。
 */
export function NoticeList({ notices, onDismiss }: { notices: QueuedNotice[]; onDismiss: (id: number) => void }) {
  const notify = useNotice();
  useEffect(() => {
    if (!notify) return;
    for (const n of notices) {
      notify(n.text, n.tone, { key: n.key });
      onDismiss(n.id);
    }
  }, [notify, notices, onDismiss]);

  if (notify || notices.length === 0) return null;
  return (
    <div className={styles.inline} role="status" aria-live="polite">
      {notices.map((n) => (
        <Alert key={n.id} tone={n.tone} title={n.text} onDismiss={() => onDismiss(n.id)} />
      ))}
    </div>
  );
}

import { useEffect } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { useNotice } from "@/components/custom/notice/notice";
import type { Notice } from "../hooks/use-shop-actions";
import styles from "../shop-page.module.css";

/** 操作结果与等待态：在外壳里交给右下角浮动提示（同一店同一操作只留一条）；单独渲染时退回表格上方的提示条。 */
export function NoticeList({ notices, onDismiss }: { notices: Notice[]; onDismiss: (id: number) => void }) {
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
    <div className={styles.notices} role="status" aria-live="polite">
      {notices.map((n) => (
        <Alert key={n.id} tone={n.tone} title={n.text} onDismiss={() => onDismiss(n.id)} />
      ))}
    </div>
  );
}

import { Alert } from "@/components/arc/alert/alert";
import type { Notice } from "../hooks/use-shop-actions";
import styles from "../shop-page.module.css";

/** 操作结果与等待态，就地显示在表格上方；可逐条关闭。 */
export function NoticeList({ notices, onDismiss }: { notices: Notice[]; onDismiss: (id: number) => void }) {
  if (notices.length === 0) return null;
  return (
    <div className={styles.notices} role="status" aria-live="polite">
      {notices.map((n) => (
        <Alert key={n.id} tone={n.tone} title={n.text} onDismiss={() => onDismiss(n.id)} />
      ))}
    </div>
  );
}

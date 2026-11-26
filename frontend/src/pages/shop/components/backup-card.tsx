import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { formatBjTime } from "@/lib/time-format";
import type { BackupState } from "../hooks/use-backup";
import styles from "../shop-page.module.css";

function sizeText(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** 数据备份卡片（ENG-06）：展开后展示最近快照，并支持手动触发。 */
export function BackupCard({ backup }: { backup: BackupState }) {
  const latest = backup.list?.items[0];
  return (
    <section className={`panel ${styles.backupCard}`} aria-label="数据备份">
      <div className={styles.backupHead}>
        <h2 className="section-title">数据备份</h2>
        <Button variant="secondary" onClick={backup.toggle}>
          {backup.open ? "收起" : "查看快照"}
        </Button>
      </div>
      {backup.open && (
        <>
          <p className={styles.backupHint}>
            {latest && backup.list
              ? `最近快照：${formatBjTime(latest.created_at)} · ${sizeText(latest.size_bytes)} · 保留最近 ${backup.list.keep} 份`
              : "暂无快照"}
          </p>
          <div>
            <Button variant="secondary" onClick={backup.run} loading={backup.pending}>
              立即备份
            </Button>
          </div>
          {backup.failed && <Alert tone="danger" title="备份失败，请查看 logs 目录下的日志" />}
          {backup.created && (
            <Alert tone="success" title={`已生成快照 ${backup.created.file_name}`} />
          )}
        </>
      )}
    </section>
  );
}

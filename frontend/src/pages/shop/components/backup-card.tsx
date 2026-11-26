import { useId } from "react";
import { ChevronRight } from "lucide-react";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { formatBjTime } from "@/lib/time-format";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { BackupState } from "../hooks/use-backup";
import styles from "../shop-page.module.css";

function sizeText(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** 数据备份卡片（ENG-06）：标题行右侧手动备份；点标题展开看最近快照。 */
export function BackupCard({ backup }: { backup: BackupState }) {
  const latest = backup.list?.items[0];
  const detailId = useId();
  return (
    <section className={`panel ${styles.backupCard}`} aria-label="数据备份">
      <div className={styles.backupHead}>
        <h2 className="section-title">
          <button
            type="button"
            className={styles.disclosure}
            aria-expanded={backup.open}
            aria-controls={backup.open ? detailId : undefined}
            onClick={backup.toggle}
          >
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
            数据备份
          </button>
        </h2>
        <Button variant="secondary" size="sm" onClick={backup.run} loading={backup.pending}>
          立即备份
        </Button>
      </div>
      {backup.open && (
        <div id={detailId}>
          {backup.loading ? (
            <Skeleton label="正在读取快照" lines={SKELETON_LINES.card} />
          ) : backup.failed ? (
            <LoadError size="sm" title="读取快照失败，请确认本地服务正常后重试" onRetry={backup.retry} />
          ) : latest && backup.list ? (
            <p className={styles.backupHint}>
              {`最近快照：${formatBjTime(latest.created_at)} · ${sizeText(latest.size_bytes)} · 保留最近 ${backup.list.keep} 份`}
            </p>
          ) : (
            <p className="panel-empty">暂无快照</p>
          )}
        </div>
      )}
    </section>
  );
}

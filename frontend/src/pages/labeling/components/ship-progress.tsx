import { Alert } from "@/components/arc/alert/alert";
import { failedRows, progressTitle, type ProgressState } from "../logic/ship-progress";
import styles from "../labeling-page.module.css";

/** 发货进度：按 SSE 逐单汇总；失败项就地列出原因。 */
export function ShipProgress({ progress }: { progress: ProgressState }) {
  if (Object.keys(progress.rows).length === 0) return null;
  const failures = failedRows(progress);
  const tone = progress.done ? (progress.failed > 0 ? "warning" : "success") : "info";
  return (
    <Alert tone={tone} title={progressTitle(progress)}>
      {failures.length > 0 && (
        <ul className={styles.reasonList}>
          {failures.map((row) => (
            <li key={row.orderId}>{row.orderNo}：{row.reason ?? "发货失败"}</li>
          ))}
        </ul>
      )}
    </Alert>
  );
}

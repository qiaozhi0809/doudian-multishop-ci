import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import styles from "./shop-failure-alert.module.css";

export interface CountMetaProps {
  /** 数据时间（ISO）；没有时不显示时间。 */
  fetchedAt: string | null | undefined;
  /** 有店没取到：写明合计不含它们。 */
  partial?: boolean;
}

/** 计数卡下面的一行：数据时间，部分店铺没取到时再写明合计口径。两样都没有时不显示。 */
export function CountMeta({ fetchedAt, partial = false }: CountMetaProps) {
  if (!fetchedAt && !partial) return null;
  return (
    <div className={styles.meta}>
      {fetchedAt && <span title={formatBjTime(fetchedAt)}>数据时间 {formatBjTimeSmart(fetchedAt)}</span>}
      {partial && <span>合计不含未取到的店铺</span>}
    </div>
  );
}

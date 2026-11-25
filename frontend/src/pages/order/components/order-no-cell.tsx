import { useCopyFeedback } from "@/components/arc/lib/use-copy-feedback";
import styles from "../order-page.module.css";

/** 订单号：等宽数字，点击复制，复制后就地显示「已复制」。 */
export function OrderNoCell({ value }: { value: string }) {
  const { state, activeKey, copy } = useCopyFeedback();
  const done = activeKey === value && state === "copied";
  const failed = activeKey === value && state === "error";
  return (
    <button type="button" className={styles.mono} title="点击复制订单号" onClick={() => void copy(value, value)}>
      {done ? <span className={styles.copied}>已复制</span> : failed ? <span className={styles.muted}>复制失败，请手动选择</span> : value}
    </button>
  );
}

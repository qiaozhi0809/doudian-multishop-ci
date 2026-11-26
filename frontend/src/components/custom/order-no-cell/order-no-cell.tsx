import { useCopyFeedback } from "@/components/arc/lib/use-copy-feedback";
import { EMPTY_TEXT } from "@/lib/empty-text";
import styles from "./order-no-cell.module.css";

export interface OrderNoCellProps {
  /** 单号；空值显示「暂无」。 */
  value: string | null | undefined;
  /** 单号的名称，用在悬停提示里，默认「订单号」。 */
  noun?: string;
}

/** 订单号 / 售后单号（全站共用）：等宽数字，点击复制，复制后就地显示「已复制」。 */
export function OrderNoCell({ value, noun = "订单号" }: OrderNoCellProps) {
  const { state, copy } = useCopyFeedback();
  if (!value) return <>{EMPTY_TEXT}</>;
  return (
    <button type="button" className={styles.no} title={`点击复制${noun}`} onClick={() => void copy(value, value)}>
      {state === "copied" ? (
        <span className={styles.copied}>已复制</span>
      ) : state === "error" ? (
        <span className={styles.failed}>复制失败，请手动选择</span>
      ) : (
        value
      )}
    </button>
  );
}

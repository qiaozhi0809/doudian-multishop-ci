import styles from "../app-shell.module.css";

/** 演练模式提示（M7）：写操作只记录请求，避免把模拟结果当成真实操作。 */
export function DryRunBanner({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className={styles.dryRunBanner} role="status">
      <span className={styles.dryRunDot} aria-hidden="true" />
      演练模式：取号、发货、打印、作废不会真的发送
    </div>
  );
}

import styles from "../app-shell.module.css";

/** 演练模式横幅（M7）：全局提示写操作只记录请求，避免把模拟结果当成真实操作。 */
export function DryRunBanner({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className={styles.dryRunBanner} role="status">
      演练模式（dry run）已开启：取号、发货、打印、作废只记录请求并返回模拟结果，不会真的发送。
      关闭后（DD_DRY_RUN=false）重启生效。
    </div>
  );
}

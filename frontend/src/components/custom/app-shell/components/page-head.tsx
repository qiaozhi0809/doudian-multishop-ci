import type { ReactNode } from "react";
import styles from "../app-shell.module.css";

interface PageHeadProps {
  title: string;
  /** 右侧的通知铃铛 */
  bell: ReactNode;
}

/** 页面标题行：左边页面标题，右边通知铃铛。不单独占一条顶栏。 */
export function PageHead({ title, bell }: PageHeadProps) {
  return (
    <header className={styles.pageHead}>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.pageHeadEnd}>{bell}</div>
    </header>
  );
}

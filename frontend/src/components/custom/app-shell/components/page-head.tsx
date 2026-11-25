import type { ReactNode } from "react";
import styles from "../app-shell.module.css";

interface PageHeadProps {
  title: string;
  health: ReactNode;
}

/** 页面标题行：左边页面标题，右边会话健康指示。不单独占一条顶栏。 */
export function PageHead({ title, health }: PageHeadProps) {
  return (
    <header className={styles.pageHead}>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.pageHeadEnd}>
        {health}
      </div>
    </header>
  );
}

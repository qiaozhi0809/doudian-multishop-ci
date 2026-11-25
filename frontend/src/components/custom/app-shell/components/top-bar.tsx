import type { ReactNode } from "react";
import styles from "../app-shell.module.css";

interface TopBarProps {
  title: string;
  filter: ReactNode;
  tasks: ReactNode;
  health: ReactNode;
  admin: ReactNode;
}

/** 顶栏：页面标题 → 店铺筛选 → 任务中心 → 会话健康指示 → 当前管理员。 */
export function TopBar({ title, filter, tasks, health, admin }: TopBarProps) {
  return (
    <header className={styles.topBar}>
      <h1 className={styles.title}>{title}</h1>
      {filter}
      <div className={styles.topBarEnd}>
        {tasks}
        {health}
        {admin}
      </div>
    </header>
  );
}

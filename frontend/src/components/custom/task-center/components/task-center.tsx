import { ListChecks, X } from "lucide-react";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/arc/popover/popover";
import { countsText, statusText, type TaskItem } from "../logic/task-log";
import styles from "../task-center.module.css";

export interface TaskCenterProps {
  tasks: TaskItem[];
  runningCount: number;
  onDismiss: (id: string) => void;
  onClearFinished: () => void;
}

/** 顶栏任务中心：进行中的取号 / 打印 / 发货批次的进度与结果。 */
export function TaskCenter({ tasks, runningCount, onDismiss, onClearFinished }: TaskCenterProps) {
  const finished = tasks.length - runningCount;
  return (
    <Popover>
      <PopoverTrigger
        className={styles.trigger}
        aria-label={runningCount > 0 ? `任务中心，${runningCount} 个进行中` : "任务中心"}
      >
        <ListChecks size={20} strokeWidth={1.75} aria-hidden="true" />
        <span className={styles.triggerText}>任务</span>
        {runningCount > 0 && (
          <Badge tone="info" size="sm">
            {runningCount}
          </Badge>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className={styles.panel}>
        <div className={styles.header}>
          <span className={styles.heading}>任务中心</span>
          {finished > 0 && (
            <Button variant="ghost" size="sm" onClick={onClearFinished}>
              清除已完成
            </Button>
          )}
        </div>
        {tasks.length === 0 ? (
          <p className={styles.empty}>没有进行中的任务；取号、打印、发货开始后，进度会显示在这里</p>
        ) : (
          <ul className={styles.list}>
            {tasks.map((task) => (
              <li key={task.id} className={styles.row}>
                <div className={styles.rowHead}>
                  <span className={styles.rowTitle}>{task.title}</span>
                  <Badge
                    tone={task.status === "running" ? "info" : task.counts.failed > 0 ? "warning" : "success"}
                    size="sm"
                  >
                    {statusText(task)}
                  </Badge>
                  {task.status === "done" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onDismiss(task.id)}
                      aria-label={`清除${task.title}任务`}
                    >
                      <X size={16} strokeWidth={1.75} aria-hidden="true" />
                    </Button>
                  )}
                </div>
                <p className={styles.counts}>{countsText(task)}</p>
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}

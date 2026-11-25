import { TaskCenter as TaskCenterView } from "./components/task-center";
import { useTaskCenter } from "./hooks/use-task-center";

/** 顶栏任务中心：装配 SSE 订阅与展示。 */
export function TaskCenter() {
  const { tasks, runningCount, dismiss, clearFinished } = useTaskCenter();
  return (
    <TaskCenterView
      tasks={tasks}
      runningCount={runningCount}
      onDismiss={dismiss}
      onClearFinished={clearFinished}
    />
  );
}

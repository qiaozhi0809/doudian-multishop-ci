import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import styles from "./load-error.module.css";

export interface LoadErrorProps {
  /** 发生了什么 + 怎么办，如「读取订单失败，请确认本地服务正常后重试」。 */
  title: string;
  onRetry: () => void;
  /** 重试按钮尺寸：整页或主列表用 md（默认），卡片、计数区、侧栏等小区块用 sm。 */
  size?: "sm" | "md";
  /** 外层容器的页面样式（如需要内边距的侧栏）。 */
  className?: string;
}

/** 读取失败（全站共用）：区块内报错提示条 + 「重新读取」。 */
export function LoadError({ title, onRetry, size = "md", className }: LoadErrorProps) {
  return (
    <div className={[styles.box, className].filter(Boolean).join(" ")}>
      <Alert tone="danger" title={title} />
      <div>
        <Button variant="secondary" size={size} onClick={onRetry}>
          重新读取
        </Button>
      </div>
    </div>
  );
}

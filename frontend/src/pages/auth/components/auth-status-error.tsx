import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";

/** 登录状态读取失败：写明原因与下一步，并提供重试。 */
export function AuthStatusError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-[var(--space-4)]">
      <Alert tone="danger" title="无法读取登录状态，请确认本地服务已启动后重试" />
      <Button variant="secondary" onClick={onRetry}>
        重新加载
      </Button>
    </div>
  );
}

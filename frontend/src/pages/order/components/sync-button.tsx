import { RefreshCw } from "lucide-react";
import { Button } from "@/components/arc/button/button";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";

export function SyncButton({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return (
    <Button loading={pending} onClick={onClick}>
      <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
      同步订单
    </Button>
  );
}

/** 同步结果：和其他页面一样走右下角浮动提示。 */
export function SyncMessage({ message, onDismiss }: { message: { tone: "success" | "info" | "danger"; text: string } | null; onDismiss: () => void }) {
  return <SyncMessageBar message={message} onDismiss={onDismiss} />;
}

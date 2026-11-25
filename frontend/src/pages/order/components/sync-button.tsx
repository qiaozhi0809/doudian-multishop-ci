import { RefreshCw } from "lucide-react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";

export function SyncButton({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return (
    <Button loading={pending} onClick={onClick}>
      <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
      同步订单
    </Button>
  );
}

export function SyncMessage({ message, onDismiss }: { message: { tone: "success" | "info" | "danger"; text: string } | null; onDismiss: () => void }) {
  if (!message) return null;
  return (
    <div role="status" aria-live="polite">
      <Alert tone={message.tone} title={message.text} onDismiss={onDismiss} />
    </div>
  );
}

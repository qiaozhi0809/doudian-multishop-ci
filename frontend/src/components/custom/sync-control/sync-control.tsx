import { useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { useNotice } from "@/components/custom/notice/notice";

export interface SyncMessage {
  tone: "success" | "warning" | "info" | "danger";
  text: string;
}

/** 只读聚合页共用的手动同步按钮与结果条（同步逻辑在各页 hooks 里）。 */
export function SyncButton({ pending, label, onClick }: { pending: boolean; label: string; onClick: () => void }) {
  return (
    <Button loading={pending} onClick={onClick}>
      <RefreshCw size={16} strokeWidth={1.75} aria-hidden="true" />
      {label}
    </Button>
  );
}

/** 同步结果：在外壳里交给右下角浮动提示；单独渲染时退回页面内提示条。 */
export function SyncMessageBar({ message, onDismiss }: { message: SyncMessage | null; onDismiss: () => void }) {
  const notify = useNotice();
  useEffect(() => {
    if (!notify || !message) return;
    notify(message.text, message.tone, { key: "sync" });
    onDismiss();
  }, [notify, message, onDismiss]);
  if (notify || !message) return null;
  return (
    <div role="status" aria-live="polite">
      <Alert tone={message.tone} title={message.text} onDismiss={onDismiss} />
    </div>
  );
}

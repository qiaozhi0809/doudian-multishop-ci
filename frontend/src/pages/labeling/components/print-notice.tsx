import { Alert } from "@/components/arc/alert/alert";

interface PrintNoticeProps {
  notice: string | null;
  summary: string | null;
  error: string | null;
  onDismissError: () => void;
}

/** 打印相关的三条提示：组件未启动（置灰原因）、批次汇总、提交失败。 */
export function PrintNotice({ notice, summary, error, onDismissError }: PrintNoticeProps) {
  if (!notice && !summary && !error) return null;
  return (
    <>
      {notice && <Alert tone="warning" title={notice} />}
      {error && <Alert tone="danger" title={error} onDismiss={onDismissError} />}
      {summary && <Alert tone="info" title={summary} />}
    </>
  );
}

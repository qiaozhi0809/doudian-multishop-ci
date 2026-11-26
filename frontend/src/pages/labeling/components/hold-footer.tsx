import { useState, type ComponentProps } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { HoldToConfirm } from "@/components/arc/hold-to-confirm/hold-to-confirm";
import { DialogFooter } from "@/components/custom/dialog-footer/dialog-footer";

type HoldProps = Pick<ComponentProps<typeof HoldToConfirm>, "label" | "confirmedLabel" | "tone" | "icon" | "onConfirm">;

interface HoldFooterProps extends HoldProps {
  busy: boolean;
  /** 提交失败的原因：显示在按钮上方，按钮复位后可以再按一次。 */
  error: string | null;
  disabled: boolean;
}

/** 打单、发货对话框的底部：失败报错 + 取消 / 按住确认。挂在对话框内容里，关闭即重置。 */
export function HoldFooter({ busy, error, disabled, onConfirm, ...hold }: HoldFooterProps) {
  const [sent, setSent] = useState(false);
  return (
    <>
      {error && <Alert tone="danger" title={error} />}
      <DialogFooter busy={busy}>
        <HoldToConfirm
          {...hold}
          confirmed={sent && !error}
          disabled={busy || disabled}
          onConfirm={() => {
            setSent(true);
            onConfirm();
          }}
        />
      </DialogFooter>
    </>
  );
}

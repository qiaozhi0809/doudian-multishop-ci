import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog } from "@/components/arc/dialog/dialog";
import { AppDialogContent } from "@/components/custom/app-dialog/app-dialog-content";
import { DialogFooter } from "@/components/custom/dialog-footer/dialog-footer";
import type { ActionResult } from "@/lib/action-result";
import { useLastPresent } from "@/lib/use-last-present";

export interface ConfirmDialogProps<T extends { id: number }> {
  /** 对着哪一项（null = 关闭）；换一项时重置报错。 */
  target: T | null | undefined;
  /** 标题写动作和对象，对象名加「」，如「停用店铺「店铺甲」」。 */
  title: (target: T) => string;
  /** 标题下的一句话，只写影响范围这类不看会出错的内容。 */
  description?: string;
  /** 动词开头，与标题的动作一致。 */
  confirmLabel: string;
  /** 危险操作：确认按钮用 danger。 */
  danger?: boolean;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (target: T) => Promise<ActionResult>;
}

/** 确认框（全站共用）：成功关闭，失败留在对话框、按钮上方报错。 */
export function ConfirmDialog<T extends { id: number }>({
  target, title, description, confirmLabel, danger, pending, onOpenChange, onConfirm,
}: ConfirmDialogProps<T>) {
  // 关闭动画期间 target 已是 null：标题沿用刚才那一项，不闪成空名字
  const shown = useLastPresent(target);
  return (
    <Dialog open={target != null} onOpenChange={onOpenChange} busy={pending}>
      <AppDialogContent size="confirm" title={shown ? title(shown) : ""} description={description}>
        {target != null && (
          <ConfirmBody
            key={target.id}
            confirmLabel={confirmLabel}
            danger={danger}
            pending={pending}
            onConfirm={() => onConfirm(target)}
            onDone={() => onOpenChange(false)}
          />
        )}
      </AppDialogContent>
    </Dialog>
  );
}

interface ConfirmBodyProps {
  confirmLabel: string;
  danger?: boolean;
  pending: boolean;
  onConfirm: () => Promise<ActionResult>;
  onDone: () => void;
}

function ConfirmBody({ confirmLabel, danger, pending, onConfirm, onDone }: ConfirmBodyProps) {
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      {error && <Alert tone="danger" title={error} />}
      <DialogFooter busy={pending}>
        <Button
          variant={danger ? "danger" : "primary"}
          loading={pending}
          onClick={async () => {
            const result = await onConfirm();
            if (result.ok) onDone();
            else setError(result.error);
          }}
        >
          {confirmLabel}
        </Button>
      </DialogFooter>
    </>
  );
}

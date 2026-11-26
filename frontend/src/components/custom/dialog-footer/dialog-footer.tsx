import type { ReactNode } from "react";
import { Button } from "@/components/arc/button/button";
import { DialogClose } from "@/components/arc/dialog/dialog";
import styles from "./dialog-footer.module.css";

export interface DialogFooterProps {
  /** 请求进行中：「取消」置灰（对话框本身由 Dialog 的 busy 挡住关闭）。 */
  busy?: boolean;
  /** 右侧的主按钮（或按住确认按钮）；危险操作用 variant="danger"。 */
  children: ReactNode;
}

/** 对话框底部按钮栏（全站共用）：ghost「取消」在左、主按钮在右，整组靠右，内容超出时贴在对话框底部。 */
export function DialogFooter({ busy = false, children }: DialogFooterProps) {
  return (
    <div className={styles.footer}>
      <DialogClose asChild>
        <Button type="button" variant="ghost" disabled={busy}>
          取消
        </Button>
      </DialogClose>
      {children}
    </div>
  );
}

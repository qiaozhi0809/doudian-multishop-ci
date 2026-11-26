import type { ComponentProps } from "react";
import { DialogContent } from "@/components/arc/dialog/dialog";
import { keepOpenOnNotice } from "@/components/custom/notice/keep-open-on-notice";
import styles from "./app-dialog.module.css";

/** 对话框三档：confirm 确认框（400）、form 表单（480）、wide 预览类（640）。 */
export type DialogSize = "confirm" | "form" | "wide";

export type AppDialogContentProps = Omit<ComponentProps<typeof DialogContent>, "variant"> & { size: DialogSize };

/**
 * 全站对话框内容（全站共用）：按档位定宽，标题区不画分隔线，正文各块纵向间距 16。
 * 只有确认框不带 ×，其余带；点右下角提示不关闭对话框。放在 Arc `Dialog` 里使用，底部按钮用 `DialogFooter`。
 */
export function AppDialogContent({ size, className, children, description, onInteractOutside, ...props }: AppDialogContentProps) {
  return (
    <DialogContent
      // 没有说明时显式声明，Radix 才不会提示缺少 Description
      {...(description ? {} : { "aria-describedby": undefined })}
      {...props}
      onInteractOutside={(event) => {
        onInteractOutside?.(event);
        keepOpenOnNotice(event);
      }}
      description={description}
      variant={size === "confirm" ? "confirm" : "default"}
      className={[styles.dialog, styles[size], className].filter(Boolean).join(" ")}
    >
      <div className={styles.body}>{children}</div>
    </DialogContent>
  );
}

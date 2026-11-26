import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import type { ActionResult } from "@/lib/action-result";
import { useLastPresent } from "@/lib/use-last-present";
import styles from "../shop-page.module.css";

interface ConfirmDialogProps {
  /** 对着哪家店（null = 关闭）；换店时重置报错。 */
  shop: { id: number; name: string } | null | undefined;
  /** 动作名，如「停用店铺」；标题 = 动作名 + 店名（全站确认框同一写法）。 */
  action: string;
  /** false：标题只用动作名（从已显示店名的弹窗里再弹出时）。 */
  shopInTitle?: boolean;
  /** 标题下的一句话，只在不看会出错时写。 */
  description?: string;
  confirmLabel: string;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<ActionResult>;
}

/** 需要二次确认的店铺操作（恢复风控暂停、停用已登录的店、开启飞鸽消息）：成功关闭，失败留在对话框、按钮上方报错。 */
export function ConfirmDialog({
  shop, action, shopInTitle = true, description, confirmLabel, pending, onOpenChange, onConfirm,
}: ConfirmDialogProps) {
  // 关闭动画期间 shop 已是 null：标题沿用刚才那家店，不闪成「停用店铺 」
  const shown = useLastPresent(shop);
  return (
    <Dialog open={shop != null} onOpenChange={onOpenChange} busy={pending}>
      <DialogContent
        title={shopInTitle ? `${action} ${shown?.name ?? ""}`.trim() : action}
        description={description}
        variant="confirm"
      >
        {shop != null && (
          <ConfirmBody key={shop.id} confirmLabel={confirmLabel} pending={pending} onConfirm={onConfirm} onDone={() => onOpenChange(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function ConfirmBody({
  confirmLabel, pending, onConfirm, onDone,
}: Pick<ConfirmDialogProps, "confirmLabel" | "pending" | "onConfirm"> & { onDone: () => void }) {
  const [error, setError] = useState<string | null>(null);
  return (
    <div className={styles.form}>
      {error && <Alert tone="danger" title={error} />}
      <div className={styles.formActions}>
        <DialogClose asChild>
          <Button type="button" variant="ghost" disabled={pending}>
            取消
          </Button>
        </DialogClose>
        <Button
          loading={pending}
          onClick={async () => {
            const r = await onConfirm();
            if (r.ok) onDone();
            else setError(r.error);
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </div>
  );
}

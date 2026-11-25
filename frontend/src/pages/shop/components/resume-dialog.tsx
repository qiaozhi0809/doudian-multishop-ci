import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";

interface ResumeDialogProps {
  shop: ShopRow | null;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

/** 恢复风控暂停需要先确认：恢复后该店会重新发起请求。 */
export function ResumeDialog({ shop, pending, onOpenChange, onConfirm }: ResumeDialogProps) {
  return (
    <Dialog open={shop !== null} onOpenChange={onOpenChange}>
      <DialogContent title="恢复店铺" description={shop?.name}>
        <div className={styles.form}>
          <p className={styles.muted}>请先确认风控问题已处理。如果仍被拦截，该店可能再次被暂停。</p>
          <div className={styles.formActions}>
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                取消
              </Button>
            </DialogClose>
            <Button loading={pending} onClick={onConfirm}>
              确认恢复
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

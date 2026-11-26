import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import { useLastPresent } from "@/lib/use-last-present";
import type { ActionResult, PoolItem } from "../hooks/use-proxy-pool";
import styles from "../proxy-pool-page.module.css";

interface DeleteDialogProps {
  item: PoolItem | null;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onConfirm: (id: number) => Promise<ActionResult>;
}

export function DeleteDialog({ item, onOpenChange, pending, onConfirm }: DeleteDialogProps) {
  const shown = useLastPresent(item);
  return (
    <Dialog open={item !== null} onOpenChange={onOpenChange} busy={pending}>
      <DialogContent title={`删除代理 ${shown?.proxy_display ?? ""}`.trim()} variant="confirm">
        {item && <DeleteBody key={item.id} item={item} pending={pending} onConfirm={onConfirm} onDone={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function DeleteBody({ item, pending, onConfirm, onDone }: Omit<DeleteDialogProps, "item" | "onOpenChange"> & { item: PoolItem; onDone: () => void }) {
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
          variant="danger"
          loading={pending}
          onClick={async () => {
            const r = await onConfirm(item.id);
            if (r.ok) onDone();
            else setError(r.error);
          }}
        >
          删除代理
        </Button>
      </div>
    </div>
  );
}

import { ConfirmDialog } from "@/components/custom/confirm-dialog/confirm-dialog";
import type { ActionResult, PoolItem } from "../hooks/use-proxy-pool";

interface DeleteDialogProps {
  item: PoolItem | null;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onConfirm: (id: number) => Promise<ActionResult>;
}

export function DeleteDialog({ item, onOpenChange, pending, onConfirm }: DeleteDialogProps) {
  return (
    <ConfirmDialog
      target={item}
      title={(target) => `删除代理「${target.proxy_display}」`}
      confirmLabel="删除代理"
      danger
      pending={pending}
      onOpenChange={onOpenChange}
      onConfirm={(target) => onConfirm(target.id)}
    />
  );
}

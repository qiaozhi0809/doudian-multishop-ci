import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogContent } from "@/components/arc/dialog/dialog";
import { Input } from "@/components/arc/input/input";
import styles from "../shop-page.module.css";

interface AddShopDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onSubmit: (input: { name: string; entity?: string; shop_no?: string }) => Promise<{ ok: true } | { ok: false; error: string }>;
}

export function AddShopDialog({ open, onOpenChange, pending, onSubmit }: AddShopDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="添加店铺" description="添加后先设置出口并检查通过，再扫码登录">
        <AddShopForm pending={pending} onSubmit={onSubmit} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function AddShopForm({ pending, onSubmit, onDone }: Pick<AddShopDialogProps, "pending" | "onSubmit"> & { onDone: () => void }) {
  const [name, setName] = useState("");
  const [entity, setEntity] = useState("");
  const [shopNo, setShopNo] = useState("");
  const [nameError, setNameError] = useState<string>();
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setNameError("请输入店铺名称");
    setNameError(undefined);
    const result = await onSubmit({
      name: name.trim(),
      ...(entity.trim() ? { entity: entity.trim() } : {}),
      ...(shopNo.trim() ? { shop_no: shopNo.trim() } : {}),
    });
    if (result.ok) onDone();
    else setError(result.error);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <Input label="店铺名称" value={name} error={nameError} onChange={(e) => setName(e.target.value)} />
      <Input label="营业执照主体（选填）" value={entity} onChange={(e) => setEntity(e.target.value)} />
      <Input label="平台店铺号（选填）" value={shopNo} onChange={(e) => setShopNo(e.target.value)} />
      {error && <Alert tone="danger" title={error} />}
      <div className={styles.formActions}>
        <Button type="submit" loading={pending}>
          添加店铺
        </Button>
      </div>
    </form>
  );
}

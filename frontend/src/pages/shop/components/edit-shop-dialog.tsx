import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogContent } from "@/components/arc/dialog/dialog";
import { Input } from "@/components/arc/input/input";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";

type Patch = { name: string; entity: string | null };
type Result = { ok: true; error: null } | { ok: false; error: string };

interface EditShopDialogProps {
  shop: ShopRow | null | undefined;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (patch: Patch) => Promise<Result>;
}

/** 改名 / 补主体。店铺号来自平台、不可编辑，因此不放在这里。 */
export function EditShopDialog({ shop, pending, onOpenChange, onSubmit }: EditShopDialogProps) {
  return (
    <Dialog open={shop != null} onOpenChange={onOpenChange}>
      <DialogContent title="编辑店铺">
        {shop && (
          <EditShopForm
            key={shop.id}
            shop={shop}
            pending={pending}
            onSubmit={onSubmit}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function EditShopForm({
  shop, pending, onSubmit, onDone,
}: { shop: ShopRow; pending: boolean; onSubmit: (p: Patch) => Promise<Result>; onDone: () => void }) {
  const [name, setName] = useState(shop.name);
  const [entity, setEntity] = useState(shop.entity ?? "");
  const [nameError, setNameError] = useState<string>();
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setNameError("请填写店铺名称");
      return;
    }
    setNameError(undefined);
    setError(null);
    const r = await onSubmit({ name: trimmed, entity: entity.trim() || null });
    if (r.ok) onDone();
    else setError(r.error);
  };

  return (
    <form onSubmit={submit}>
      <Input label="店铺名称" value={name} error={nameError} onChange={(e) => setName(e.target.value)} />
      <Input
        label="营业执照主体（选填）"
        value={entity}
        onChange={(e) => setEntity(e.target.value)}
      />
      {error && <Alert tone="danger" title={error} />}
      <div className={styles.formActions}>
        <Button type="submit" loading={pending}>
          保存
        </Button>
      </div>
    </form>
  );
}

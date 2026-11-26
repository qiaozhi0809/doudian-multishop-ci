import { useState, type FormEvent } from "react";
import { useLastPresent } from "@/lib/use-last-present";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog } from "@/components/arc/dialog/dialog";
import { AppDialogContent } from "@/components/custom/app-dialog/app-dialog-content";
import { DialogFooter } from "@/components/custom/dialog-footer/dialog-footer";
import { Input } from "@/components/arc/input/input";
import { PasswordField } from "@/components/arc/password-field/password-field";
import type { ActionResult, PoolItem, PoolPatch } from "../hooks/use-proxy-pool";
import { buildPatch, initialEditForm, type EditField, type EditForm } from "../logic/edit-form";
import styles from "../proxy-pool-page.module.css";

interface EditDialogProps {
  item: PoolItem | null;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onSave: (id: number, patch: PoolPatch) => Promise<ActionResult>;
}

export function EditDialog({ item, onOpenChange, pending, onSave }: EditDialogProps) {
  const shown = useLastPresent(item);
  return (
    <Dialog open={item !== null} onOpenChange={onOpenChange} busy={pending}>
      <AppDialogContent size="form" title="编辑代理" description={shown?.proxy_display}>
        {item && <EditForm key={item.id} item={item} pending={pending} onSave={onSave} onDone={() => onOpenChange(false)} />}
      </AppDialogContent>
    </Dialog>
  );
}

type FormProps = Omit<EditDialogProps, "item" | "onOpenChange"> & { item: PoolItem; onDone: () => void };

function EditForm({ item, pending, onSave, onDone }: FormProps) {
  const [form, setForm] = useState<EditForm>(() => initialEditForm(item));
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<EditField, string>>>({});
  const set = (p: Partial<EditForm>) => {
    setForm((f) => ({ ...f, ...p }));
    setError(null);
    setFieldErrors({});
  };

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const built = buildPatch(item, form);
    if (!built.ok) {
      if (built.field) setFieldErrors({ [built.field]: built.error });
      else setError(built.error);
      return;
    }
    const result = await onSave(item.id, built.patch);
    if (result.ok) onDone();
    else setError(result.error);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {item.in_use_by && <Alert tone="warning" title={`正被店铺「${item.in_use_by.shop_name}」使用，修改地址或账号密码后该店出口需要重新检查`} />}
      <div className={styles.formRow}>
        <Input label="主机" value={form.host} error={fieldErrors.host} onChange={(e) => set({ host: e.target.value })} />
        <Input label="端口" inputMode="numeric" value={form.port} error={fieldErrors.port} onChange={(e) => set({ port: e.target.value })} />
      </div>
      <Input label="账号" placeholder="留空表示不改" autoComplete="off" value={form.username} onChange={(e) => set({ username: e.target.value })} />
      <PasswordField label="密码" placeholder="留空表示不改" autoComplete="new-password" value={form.password} onChange={(e) => set({ password: e.target.value })} />
      <Input label="到期日" type="date" description="清空表示不限期" value={form.expires_at} onChange={(e) => set({ expires_at: e.target.value })} />
      {error && <Alert tone="danger" title={error} />}
      <DialogFooter busy={pending}>
        <Button type="submit" loading={pending}>
          保存
        </Button>
      </DialogFooter>
    </form>
  );
}

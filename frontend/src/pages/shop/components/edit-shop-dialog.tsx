import { useState, type FormEvent } from "react";
import { useLastPresent } from "@/lib/use-last-present";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import { Input } from "@/components/arc/input/input";
import type { ActionResult } from "@/lib/action-result";
import type { ShopRow } from "@/lib/use-shops";
import type { ShopPatch } from "../hooks/use-shop-actions";
import { BANK_NAME_MAX, buildShopPatch, shopFieldErrors } from "../logic/shop-fields";
import styles from "../shop-page.module.css";

interface EditShopDialogProps {
  shop: ShopRow | null | undefined;
  pending: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (patch: ShopPatch) => Promise<ActionResult>;
}

/** 编辑店铺：本地别名，以及平台没有稳定接口、需要手工维护的主体、店铺ID、收款账户。 */
export function EditShopDialog({ shop, pending, onOpenChange, onSubmit }: EditShopDialogProps) {
  const shown = useLastPresent(shop);
  return (
    <Dialog open={shop != null} onOpenChange={onOpenChange} busy={pending}>
      <DialogContent title="编辑店铺" description={shown?.name}>
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
}: Pick<EditShopDialogProps, "pending" | "onSubmit"> & { shop: ShopRow; onDone: () => void }) {
  const [name, setName] = useState(shop.name);
  const [entity, setEntity] = useState(shop.entity ?? "");
  const [platformShopId, setPlatformShopId] = useState(shop.platform_shop_id ?? "");
  const [bankName, setBankName] = useState(shop.bank_name ?? "");
  const [bankTail, setBankTail] = useState(shop.bank_tail ?? "");
  const [nameError, setNameError] = useState<string>();
  const [idError, setIdError] = useState<string>();
  const [tailError, setTailError] = useState<string>();
  const [bankNameError, setBankNameError] = useState<string>();
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const values = { name, entity, platformShopId, bankName, bankTail };
    const errors = shopFieldErrors(shop, values);
    setNameError(errors.name);
    setIdError(errors.id);
    setBankNameError(errors.bankName);
    setTailError(errors.tail);
    if (errors.name || errors.id || errors.bankName || errors.tail) return;
    setError(null);
    // 只发有改动的字段：旧的不合规数据不改就不会挡住保存
    const patch = buildShopPatch(shop, values);
    if (Object.keys(patch).length === 0) return onDone();
    const r = await onSubmit(patch);
    if (r.ok) onDone();
    else setError(r.error);
  };

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <Input label="店铺名称" value={name} error={nameError} onChange={(e) => setName(e.target.value)} />
      <Input label="主体" optional value={entity} onChange={(e) => setEntity(e.target.value)} />
      <Input
        label="店铺ID"
        optional
        inputMode="numeric"
        maxLength={20}
        value={platformShopId}
        error={idError}
        onChange={(e) => {
          setPlatformShopId(e.target.value);
          setIdError(undefined);
        }}
      />
      <Input
        label="开户行"
        optional
        maxLength={BANK_NAME_MAX}
        value={bankName}
        error={bankNameError}
        onChange={(e) => {
          setBankName(e.target.value);
          setBankNameError(undefined);
        }}
      />
      <Input
        label="卡号尾号"
        optional
        inputMode="numeric"
        maxLength={4}
        value={bankTail}
        error={tailError}
        onChange={(e) => {
          setBankTail(e.target.value.replace(/\D/g, "").slice(0, 4));
          setTailError(undefined);
        }}
      />
      {error && <Alert tone="danger" title={error} />}
      <div className={styles.formActions}>
        <DialogClose asChild>
          <Button type="button" variant="ghost" disabled={pending}>
            取消
          </Button>
        </DialogClose>
        <Button type="submit" loading={pending}>
          保存
        </Button>
      </div>
    </form>
  );
}

import { useState, type FormEvent } from "react";
import { useLastPresent } from "@/lib/use-last-present";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import type { ShopRow } from "@/lib/use-shops";
import type { ActionResult } from "@/lib/action-result";
import type { components } from "@/lib/api-types";
import { buildEgressRequest, directDisabledReason, emptyEgressForm, type EgressField, type EgressForm } from "../logic/egress-form";
import styles from "../shop-page.module.css";
import { EgressFields } from "./egress-fields";

type EgressRequest = components["schemas"]["EgressRequest"];

interface EgressDialogProps {
  shop: ShopRow | null;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  /** 当前所有店铺，用来判断是否还能选直连。 */
  shops: ShopRow[];
  onSave: (request: EgressRequest) => Promise<ActionResult>;
  onAcceptChange: () => void;
}

export function EgressDialog({ shop, onOpenChange, pending, shops, onSave, onAcceptChange }: EgressDialogProps) {
  const shown = useLastPresent(shop);
  return (
    <Dialog open={shop !== null} onOpenChange={onOpenChange} busy={pending}>
      <DialogContent title="设置出口" description={shown?.name}>
        {shop && (
          <EgressDialogBody
            key={shop.id}
            shop={shop}
            pending={pending}
            shops={shops}
            onSave={onSave}
            onAcceptChange={onAcceptChange}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

type BodyProps = Omit<EgressDialogProps, "shop" | "onOpenChange"> & { shop: ShopRow; onDone: () => void };

function EgressDialogBody({ shop, pending, shops, onSave, onAcceptChange, onDone }: BodyProps) {
  const directReason = directDisabledReason(shops, shop.id);
  const [form, setForm] = useState<EgressForm>(() => ({ ...emptyEgressForm(), mode: shop.egress_mode ?? "proxy" }));
  const [errors, setErrors] = useState<Partial<Record<EgressField, string>>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  const patch = (p: Partial<EgressForm>) => {
    setForm((f) => ({ ...f, ...p }));
    setErrors({});
    setServerError(null);
  };

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const built = buildEgressRequest(form);
    if (!built.ok) return setErrors(built.errors);
    const result = await onSave(built.request);
    if (result.ok) onDone();
    else setServerError(result.error);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      {shop.status === "active" && <Alert tone="warning" title="该店已登录，修改出口后需要重新扫码" />}
      {shop.egress_status === "changed" && (
        <Alert tone="warning" title={`检查到出口 IP 已变为 ${shop.egress_ip_pending ?? "新的地址"}，确认后才能继续使用`}>
          <Button type="button" variant="secondary" size="sm" onClick={onAcceptChange}>
            确认新 IP
          </Button>
        </Alert>
      )}
      {/* 直连被别的店占用时禁用该项，原因放在悬停提示里 */}
      <div title={directReason ?? undefined}>
        <SegmentedControl
          label="出口方式"
          value={form.mode}
          onValueChange={(mode) => patch({ mode: mode as EgressForm["mode"] })}
          options={[
            { value: "proxy", label: "代理" },
            { value: "direct", label: "直连", disabled: directReason !== null },
          ]}
        />
      </div>
      <EgressFields form={form} errors={errors} onChange={patch} />
      {serverError && <Alert tone="danger" title={serverError} />}
      <div className={styles.formActions}>
        <DialogClose asChild>
          <Button type="button" variant="ghost" disabled={pending}>
            取消
          </Button>
        </DialogClose>
        <Button type="submit" loading={pending}>
          保存出口
        </Button>
      </div>
    </form>
  );
}

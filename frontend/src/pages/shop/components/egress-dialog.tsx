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
import { isLoggedIn } from "../logic/shop-status";
import styles from "../shop-page.module.css";
import { ConfirmDialog } from "./confirm-dialog";
import { EgressFields } from "./egress-fields";
import { ReasonTip } from "./reason-tip";

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
  /** 已登录的店改出口要重新扫码：校验通过后先放这里，确认了才提交。 */
  const [confirming, setConfirming] = useState<EgressRequest | null>(null);
  const loggedIn = isLoggedIn(shop);

  const patch = (p: Partial<EgressForm>) => {
    setForm((f) => ({ ...f, ...p }));
    setErrors({});
    setServerError(null);
  };

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const built = buildEgressRequest(form);
    if (!built.ok) return setErrors(built.errors);
    if (loggedIn) return setConfirming(built.request);
    const result = await save(built.request);
    if (!result.ok) setServerError(result.error);
  }

  async function save(request: EgressRequest) {
    const result = await onSave(request);
    if (result.ok) onDone();
    return result;
  }

  return (
    <>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        {loggedIn && <Alert tone="warning" title="该店已登录，修改出口后需要重新扫码" />}
        {shop.egress_status === "changed" && (
          <Alert tone="warning" title={`检查到出口 IP 已变为 ${shop.egress_ip_pending ?? "新的地址"}，接受后才能继续使用`}>
            <Button type="button" variant="secondary" size="sm" onClick={onAcceptChange}>
              接受新 IP
            </Button>
          </Alert>
        )}
        {/* 直连被别的店占用时禁用该项，原因放在提示气泡里 */}
        <ReasonTip reason={directReason}>
          <SegmentedControl
            label="出口方式"
            value={form.mode}
            onValueChange={(mode) => patch({ mode: mode as EgressForm["mode"] })}
            options={[
              { value: "proxy", label: "代理" },
              { value: "direct", label: "直连", disabled: directReason !== null },
            ]}
          />
        </ReasonTip>
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
      <ConfirmDialog
        shop={confirming ? shop : null}
        action="修改出口"
        description="保存后需要重新扫码登录"
        confirmLabel="保存出口"
        danger
        pending={pending}
        onOpenChange={(open) => !open && setConfirming(null)}
        onConfirm={() => save(confirming!)}
      />
    </>
  );
}

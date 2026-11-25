import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import type { ShopRow } from "@/lib/use-shops";
import { buildEgressRequest, emptyEgressForm, type EgressField, type EgressForm } from "../logic/egress-form";
import type { components } from "@/lib/api-types";
import styles from "../shop-page.module.css";
import { EgressFields } from "./egress-fields";

type EgressRequest = components["schemas"]["EgressRequest"];

interface EgressDialogProps {
  shop: ShopRow | null;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  onSave: (request: EgressRequest) => Promise<{ ok: boolean; error: string | null }>;
  onAcceptChange: () => void;
}

export function EgressDialog({ shop, onOpenChange, pending, onSave, onAcceptChange }: EgressDialogProps) {
  return (
    <Dialog open={shop !== null} onOpenChange={onOpenChange}>
      <DialogContent title="设置出口" description={shop ? `${shop.name}：每家店使用固定的出口 IP，不能与其他店重复` : undefined}>
        {shop && (
          <EgressDialogBody
            key={shop.id}
            shop={shop}
            pending={pending}
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

function EgressDialogBody({ shop, pending, onSave, onAcceptChange, onDone }: BodyProps) {
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
          <Button variant="secondary" size="sm" onClick={onAcceptChange}>
            确认新 IP
          </Button>
        </Alert>
      )}
      <SegmentedControl
        label="出口方式"
        value={form.mode}
        onValueChange={(mode) => patch({ mode: mode as EgressForm["mode"] })}
        options={[
          { value: "proxy", label: "代理" },
          { value: "direct", label: "直连" },
        ]}
      />
      {form.mode === "direct" && <Alert tone="info" title="直连使用本机网络出口，同一时间只允许一家店直连" />}
      <EgressFields form={form} errors={errors} onChange={patch} />
      {serverError && <Alert tone="danger" title={serverError} />}
      <div className={styles.formActions}>
        <DialogClose asChild>
          <Button type="button" variant="ghost">
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

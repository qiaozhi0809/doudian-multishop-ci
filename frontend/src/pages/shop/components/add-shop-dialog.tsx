import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogContent } from "@/components/arc/dialog/dialog";
import { Input } from "@/components/arc/input/input";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";
import { buildEgressRequest, emptyEgressForm, type EgressField, type EgressForm } from "../logic/egress-form";
import styles from "../shop-page.module.css";
import { EgressFields } from "./egress-fields";

type ShopCreate = components["schemas"]["ShopCreate"];
type EgressChoice = "none" | "pool" | "paste" | "direct";

interface AddShopDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  /** 当前所有店铺，用来判断是否还能选直连。 */
  shops: ShopRow[];
  onSubmit: (input: ShopCreate) => Promise<{ ok: true } | { ok: false; error: string }>;
}

export function AddShopDialog({ open, onOpenChange, pending, shops, onSubmit }: AddShopDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="添加店铺">
        <AddShopForm pending={pending} shops={shops} onSubmit={onSubmit} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

/** 把「出口方式」选项落到出口表单上。 */
const FORM_PATCH: Record<Exclude<EgressChoice, "none">, Partial<EgressForm>> = {
  pool: { mode: "proxy", entry: "pool" },
  paste: { mode: "proxy", entry: "paste" },
  direct: { mode: "direct" },
};

function AddShopForm({ pending, shops, onSubmit, onDone }: Pick<AddShopDialogProps, "pending" | "shops" | "onSubmit"> & { onDone: () => void }) {
  const [name, setName] = useState("");
  const [entity, setEntity] = useState("");
  const [shopNo, setShopNo] = useState("");
  const [nameError, setNameError] = useState<string>();
  const [error, setError] = useState<string | null>(null);
  const [choice, setChoice] = useState<EgressChoice>("none");
  const [egress, setEgress] = useState<EgressForm>(emptyEgressForm);
  const [egressErrors, setEgressErrors] = useState<Partial<Record<EgressField, string>>>({});

  const directHolder = shops.find((s) => s.egress_mode === "direct" && s.status !== "disabled");

  function pick(next: EgressChoice) {
    setChoice(next);
    setEgressErrors({});
    if (next !== "none") setEgress((f) => ({ ...f, ...FORM_PATCH[next] }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setNameError("请输入店铺名称");
    setNameError(undefined);
    let request: ShopCreate["egress"];
    if (choice !== "none") {
      const built = buildEgressRequest(egress);
      if (!built.ok) return setEgressErrors(built.errors);
      request = built.request;
    }
    const result = await onSubmit({
      name: name.trim(),
      ...(entity.trim() ? { entity: entity.trim() } : {}),
      ...(shopNo.trim() ? { shop_no: shopNo.trim() } : {}),
      ...(request ? { egress: request } : {}),
    });
    if (result.ok) onDone();
    else setError(result.error);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <Input label="店铺名称" value={name} error={nameError} onChange={(e) => setName(e.target.value)} />
      <Input label="营业执照主体（选填）" value={entity} onChange={(e) => setEntity(e.target.value)} />
      <Input label="平台店铺号（选填）" value={shopNo} onChange={(e) => setShopNo(e.target.value)} />
      <SegmentedControl
        label="出口（选填）"
        showLabel
        value={choice}
        onValueChange={(v) => pick(v as EgressChoice)}
        options={[
          { value: "none", label: "暂不设置" },
          { value: "pool", label: "从池选择" },
          { value: "paste", label: "粘贴代理" },
          { value: "direct", label: "直连", disabled: directHolder !== undefined },
        ]}
      />
      {directHolder && <Alert tone="info" title={`已有店铺「${directHolder.name}」使用直连，最多一家店可直连`} />}
      {choice !== "none" && (
        <EgressFields
          form={egress}
          errors={egressErrors}
          showEntrySwitch={false}
          onChange={(p) => {
            setEgress((f) => ({ ...f, ...p }));
            setEgressErrors({});
          }}
        />
      )}
      {error && <Alert tone="danger" title={error} />}
      <div className={styles.formActions}>
        <Button type="submit" loading={pending}>
          添加店铺
        </Button>
      </div>
    </form>
  );
}

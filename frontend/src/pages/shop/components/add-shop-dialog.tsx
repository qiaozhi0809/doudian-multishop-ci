import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import { Input } from "@/components/arc/input/input";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";
import { buildEgressRequest, directDisabledReason, emptyEgressForm, type EgressField, type EgressForm } from "../logic/egress-form";
import { platformShopIdError } from "../logic/shop-fields";
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
    <Dialog open={open} onOpenChange={onOpenChange} busy={pending}>
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
  const [platformShopId, setPlatformShopId] = useState("");
  const [nameError, setNameError] = useState<string>();
  const [idError, setIdError] = useState<string>();
  const [error, setError] = useState<string | null>(null);
  const [choice, setChoice] = useState<EgressChoice>("none");
  const [egress, setEgress] = useState<EgressForm>(emptyEgressForm);
  const [egressErrors, setEgressErrors] = useState<Partial<Record<EgressField, string>>>({});

  const directReason = directDisabledReason(shops);

  function pick(next: EgressChoice) {
    setChoice(next);
    setEgressErrors({});
    if (next !== "none") setEgress((f) => ({ ...f, ...FORM_PATCH[next] }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const id = platformShopId.trim();
    setNameError(name.trim() ? undefined : "请输入店铺名称");
    setIdError(platformShopIdError(id));
    if (!name.trim() || platformShopIdError(id)) return;
    let request: ShopCreate["egress"];
    if (choice !== "none") {
      const built = buildEgressRequest(egress);
      if (!built.ok) return setEgressErrors(built.errors);
      request = built.request;
    }
    const result = await onSubmit({
      name: name.trim(),
      ...(entity.trim() ? { entity: entity.trim() } : {}),
      ...(id ? { platform_shop_id: id } : {}),
      ...(request ? { egress: request } : {}),
    });
    if (result.ok) onDone();
    else setError(result.error);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
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
      {/* 直连被别的店占用时禁用该项，原因放在悬停提示里 */}
      <div title={directReason ?? undefined}>
        <SegmentedControl
          label="出口"
          showLabel
          optional
          value={choice}
          onValueChange={(v) => pick(v as EgressChoice)}
          options={[
            { value: "none", label: "暂不设置" },
            { value: "pool", label: "从池选择" },
            { value: "paste", label: "粘贴代理" },
            { value: "direct", label: "直连", disabled: directReason !== null },
          ]}
        />
      </div>
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
        <DialogClose asChild>
          <Button type="button" variant="ghost" disabled={pending}>
            取消
          </Button>
        </DialogClose>
        <Button type="submit" loading={pending}>
          添加店铺
        </Button>
      </div>
    </form>
  );
}

import { PoolSelect } from "@/components/custom/pool-select/pool-select";
import { Input } from "@/components/arc/input/input";
import { PasswordField } from "@/components/arc/password-field/password-field";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Textarea } from "@/components/arc/textarea/textarea";
import type { EgressField, EgressForm } from "../logic/egress-form";
import styles from "../shop-page.module.css";

interface EgressFieldsProps {
  form: EgressForm;
  errors: Partial<Record<EgressField, string>>;
  onChange: (patch: Partial<EgressForm>) => void;
  /** 是否显示「从池选择 / 粘贴 / 手填」切换；添加店铺时由外层的出口方式自行切换。 */
  showEntrySwitch?: boolean;
}

const PASSWORD_LABELS = { showPassword: "显示密码", hidePassword: "隐藏密码" };

/** 出口设置的输入区：直连无需填写；代理可从池里选、粘贴代理商一行，或手填（只接受 http / https）。 */
export function EgressFields({ form, errors, onChange, showEntrySwitch = true }: EgressFieldsProps) {
  if (form.mode === "direct") return null;
  return (
    <>
      {showEntrySwitch && (
        <SegmentedControl
          label="填写方式"
          value={form.entry}
          onValueChange={(entry) => onChange({ entry: entry as EgressForm["entry"] })}
          options={[
            { value: "pool", label: "从池选择" },
            { value: "paste", label: "粘贴" },
            { value: "fields", label: "手填" },
          ]}
        />
      )}
      {form.entry === "pool" ? (
        <PoolSelect value={form.poolId} error={errors.poolId} onChange={(poolId) => onChange({ poolId })} />
      ) : form.entry === "paste" ? (
        <Textarea
          label="代理商格式"
          description="格式：IP|端口|账号|密码|到期日（YYYY-MM-DD）"
          rows={3}
          value={form.paste}
          error={errors.paste}
          onChange={(e) => onChange({ paste: e.target.value })}
        />
      ) : (
        <>
          <SegmentedControl
            label="协议"
            value={form.scheme}
            onValueChange={(scheme) => onChange({ scheme: scheme as EgressForm["scheme"] })}
            options={[
              { value: "http", label: "http" },
              { value: "https", label: "https" },
            ]}
          />
          <div className={styles.formRow}>
            <Input label="代理主机" value={form.host} error={errors.host} onChange={(e) => onChange({ host: e.target.value })} />
            <Input label="端口" inputMode="numeric" value={form.port} error={errors.port} onChange={(e) => onChange({ port: e.target.value })} />
          </div>
          <Input label="账号" optional autoComplete="off" value={form.username} onChange={(e) => onChange({ username: e.target.value })} />
          <PasswordField
            label="密码"
            autoComplete="off"
            messages={PASSWORD_LABELS}
            value={form.password}
            error={errors.password}
            onChange={(e) => onChange({ password: e.target.value })}
          />
          <Input
            label="到期日"
            optional
            type="date"
            value={form.expiresAt}
            error={errors.expiresAt}
            onChange={(e) => onChange({ expiresAt: e.target.value })}
          />
        </>
      )}
    </>
  );
}

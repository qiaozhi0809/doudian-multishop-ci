import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogContent } from "@/components/arc/dialog/dialog";
import { PasswordField } from "@/components/arc/password-field/password-field";
import { validatePassword } from "@/pages/auth/logic/auth-messages";
import styles from "../app-shell.module.css";

interface ChangePasswordDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (oldPassword: string, newPassword: string) => Promise<boolean>;
  pending: boolean;
  error: string | null;
  succeeded: boolean;
}

/** 修改密码：成功与失败都在对话框内就地提示（不用 toast）。 */
export function ChangePasswordDialog({ open, onOpenChange, onSubmit, pending, error, succeeded }: ChangePasswordDialogProps) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [oldError, setOldError] = useState<string>();
  const [newError, setNewError] = useState<string>();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const oldProblem = oldPassword ? undefined : "请输入原密码";
    const newProblem = validatePassword(newPassword) ?? undefined;
    setOldError(oldProblem);
    setNewError(newProblem);
    if (oldProblem || newProblem) return;
    if (await onSubmit(oldPassword, newPassword)) {
      setOldPassword("");
      setNewPassword("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="修改密码">
        <form onSubmit={handleSubmit} noValidate className={styles.dialogForm}>
          <PasswordField
            label="原密码"
            name="old_password"
            autoComplete="current-password"
            value={oldPassword}
            aria-invalid={oldError ? true : undefined}
            description={oldError}
            messages={{ showPassword: "显示密码", hidePassword: "隐藏密码" }}
            onChange={(e) => {
              setOldPassword(e.target.value);
              setOldError(undefined);
            }}
          />
          <PasswordField
            label="新密码"
            name="new_password"
            autoComplete="new-password"
            value={newPassword}
            aria-invalid={newError ? true : undefined}
            description={newError}
            messages={{ showPassword: "显示密码", hidePassword: "隐藏密码" }}
            onChange={(e) => {
              setNewPassword(e.target.value);
              setNewError(undefined);
            }}
          />
          {error && <Alert tone="danger" title={error} />}
          {succeeded && <Alert tone="success" title="密码已修改，其他设备需要重新登录" />}
          <Button type="submit" loading={pending}>
            修改密码
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

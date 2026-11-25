import { useState, type FormEvent } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Card } from "@/components/arc/card/card";
import { Input } from "@/components/arc/input/input";
import { PasswordField } from "@/components/arc/password-field/password-field";
import { validatePassword } from "../logic/auth-messages";

export interface CredentialsFormProps {
  title: string;
  description?: string;
  submitLabel: string;
  passwordAutoComplete: "current-password" | "new-password";
  pending: boolean;
  /** 服务端返回的失败原因，已转成可读文案 */
  error: string | null;
  onSubmit: (username: string, password: string) => void;
  onEdit: () => void;
}

/** 账号 + 密码表单，登录与创建管理员共用。提交前先校验（账号必填、密码至少 8 位）。 */
export function CredentialsForm(props: CredentialsFormProps) {
  const { title, description, submitLabel, passwordAutoComplete, pending, error, onSubmit, onEdit } = props;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [usernameError, setUsernameError] = useState<string>();
  const [passwordError, setPasswordError] = useState<string>();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const nameProblem = username.trim() ? undefined : "请输入账号";
    const passwordProblem = validatePassword(password) ?? undefined;
    setUsernameError(nameProblem);
    setPasswordError(passwordProblem);
    if (nameProblem || passwordProblem) return;
    onSubmit(username.trim(), password);
  }

  return (
    <Card title={title} description={description}>
      <form onSubmit={handleSubmit} noValidate className="mt-[var(--space-4)] flex flex-col gap-[var(--space-4)]">
        <Input
          label="账号"
          name="username"
          autoComplete="username"
          value={username}
          error={usernameError}
          onChange={(e) => {
            setUsername(e.target.value);
            setUsernameError(undefined);
            onEdit();
          }}
        />
        <PasswordField
          label="密码"
          name="password"
          autoComplete={passwordAutoComplete}
          value={password}
          messages={{ showPassword: "显示密码", hidePassword: "隐藏密码" }}
          aria-invalid={passwordError ? true : undefined}
          description={passwordError}
          onChange={(e) => {
            setPassword(e.target.value);
            setPasswordError(undefined);
            onEdit();
          }}
        />
        {error && <Alert tone="danger" title={error} />}
        <Button type="submit" loading={pending}>
          {submitLabel}
        </Button>
      </form>
    </Card>
  );
}

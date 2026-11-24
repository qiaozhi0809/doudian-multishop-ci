import { CredentialsForm, type CredentialsFormProps } from "./credentials-form";

type Props = Pick<CredentialsFormProps, "pending" | "error" | "onSubmit" | "onEdit">;

export function SetupForm(props: Props) {
  return (
    <CredentialsForm
      title="创建管理员"
      description="首次使用，请创建本机管理员账号，密码至少 8 位"
      submitLabel="创建账号"
      passwordAutoComplete="new-password"
      {...props}
    />
  );
}

import { CredentialsForm, type CredentialsFormProps } from "./credentials-form";

type Props = Pick<CredentialsFormProps, "pending" | "error" | "onSubmit" | "onEdit">;

export function LoginForm(props: Props) {
  return (
    <CredentialsForm
      title="登录"
      submitLabel="登录"
      passwordAutoComplete="current-password"
      {...props}
    />
  );
}

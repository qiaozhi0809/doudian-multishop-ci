import { Navigate } from "react-router-dom";
import { AuthAside } from "./components/auth-aside";
import { AuthLayout } from "./components/auth-layout";
import { AuthLoading } from "./components/auth-loading";
import { AuthStatusError } from "./components/auth-status-error";
import { AuthSuccess } from "./components/auth-success";
import { LoginForm } from "./components/login-form";
import { SetupForm } from "./components/setup-form";
import { useAuth } from "./hooks/use-auth";
import { useAuthRedirect } from "./hooks/use-auth-redirect";
import { useSuccessHold } from "./hooks/use-success-hold";

export default function AuthPage({ mode }: { mode: "login" | "setup" }) {
  const gate = useAuthRedirect();
  const auth = useAuth();
  const hold = useSuccessHold();

  // 成功后先播完成动画，播完再跳转
  if (gate.target && !hold.holding) return <Navigate to={gate.target} replace />;

  const view = hold.done ? "done" : gate.isError ? "error" : gate.isLoading ? "loading" : mode;
  const formProps = { pending: auth.pending, error: auth.error, onEdit: auth.clearError };
  const content = {
    done: <AuthSuccess title={mode === "setup" ? "管理员已创建" : "登录成功"} />,
    error: <AuthStatusError onRetry={() => void gate.refetch()} />,
    loading: <AuthLoading />,
    setup: <SetupForm {...formProps} onSubmit={(u, p) => void hold.run(() => auth.setup(u, p))} />,
    login: <LoginForm {...formProps} onSubmit={(u, p) => void hold.run(() => auth.login(u, p))} />,
  }[view];

  return (
    <AuthLayout view={view} aside={<AuthAside />}>
      {content}
    </AuthLayout>
  );
}

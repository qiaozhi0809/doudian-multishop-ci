import { Navigate } from "react-router-dom";
import { AuthLayout } from "./components/auth-layout";
import { AuthLoading } from "./components/auth-loading";
import { AuthStatusError } from "./components/auth-status-error";
import { LoginForm } from "./components/login-form";
import { SetupForm } from "./components/setup-form";
import { useAuth } from "./hooks/use-auth";
import { useAuthRedirect } from "./hooks/use-auth-redirect";

export default function AuthPage({ mode }: { mode: "login" | "setup" }) {
  const gate = useAuthRedirect();
  const auth = useAuth();

  if (gate.target) return <Navigate to={gate.target} replace />;
  if (gate.isError) {
    return (
      <AuthLayout>
        <AuthStatusError onRetry={() => void gate.refetch()} />
      </AuthLayout>
    );
  }
  if (gate.isLoading) {
    return (
      <AuthLayout>
        <AuthLoading />
      </AuthLayout>
    );
  }

  const formProps = {
    pending: auth.pending,
    error: auth.error,
    onEdit: auth.clearError,
  };
  return (
    <AuthLayout>
      {mode === "setup" ? (
        <SetupForm {...formProps} onSubmit={(u, p) => void auth.setup(u, p)} />
      ) : (
        <LoginForm {...formProps} onSubmit={(u, p) => void auth.login(u, p)} />
      )}
    </AuthLayout>
  );
}

import { Navigate, Outlet } from "react-router-dom";
import { AuthLayout } from "./components/auth-layout";
import { AuthLoading } from "./components/auth-loading";
import { AuthStatusError } from "./components/auth-status-error";
import { useAuthRedirect } from "./hooks/use-auth-redirect";

/** 路由守卫：未初始化 → /setup；未登录 → /login?next=…；已登录放行。 */
export function RequireAuth() {
  const gate = useAuthRedirect();
  if (gate.target) return <Navigate to={gate.target} replace />;
  if (gate.isError) {
    return (
      <AuthLayout view="error">
        <AuthStatusError onRetry={() => void gate.refetch()} />
      </AuthLayout>
    );
  }
  if (gate.isLoading) {
    return (
      <AuthLayout view="loading">
        <AuthLoading />
      </AuthLayout>
    );
  }
  return <Outlet />;
}

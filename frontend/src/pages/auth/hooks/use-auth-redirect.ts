import { useLocation } from "react-router-dom";
import { resolveAuthRoute } from "../logic/auth-route";
import { useAuth } from "./use-auth";

/** 当前路径在当前登录状态下应跳去哪里（null 表示留下）。状态未就绪时为 null 并带上加载 / 出错标记。 */
export function useAuthRedirect() {
  const auth = useAuth();
  const location = useLocation();
  const target = auth.status ? resolveAuthRoute(auth.status, location.pathname + location.search) : null;
  return { target, isLoading: auth.isLoading, isError: auth.isError, refetch: auth.refetch };
}

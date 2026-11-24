export interface AuthState {
  setup_required: boolean;
  logged_in: boolean;
}

export const DEFAULT_HOME = "/orders";

/** next 只接受站内绝对路径，且不能回到 /login、/setup，防止开放重定向与循环。 */
function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return DEFAULT_HOME;
  const pathname = raw.split(/[?#]/)[0];
  if (pathname === "/login" || pathname === "/setup") return DEFAULT_HOME;
  return raw;
}

/**
 * 根据登录状态决定当前路径是否需要跳转；返回 null 表示留在原地。
 * `path` 为 pathname + search，例如 `/shops?shops=1`。
 */
export function resolveAuthRoute(status: AuthState, path: string): string | null {
  const [pathname, search = ""] = path.split("?");
  const onAuthPage = pathname === "/login" || pathname === "/setup";

  if (status.setup_required) return pathname === "/setup" ? null : "/setup";
  if (!status.logged_in) {
    if (pathname === "/login") return null;
    if (pathname === "/setup") return "/login";
    return `/login?next=${encodeURIComponent(path)}`;
  }
  if (onAuthPage) return safeNext(new URLSearchParams(search).get("next"));
  return null;
}

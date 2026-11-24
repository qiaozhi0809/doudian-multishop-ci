import { useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { authErrorMessage, type AuthAction } from "../logic/auth-messages";

export type AuthStatus = components["schemas"]["AuthStatus"];

const LOGGED_OUT: AuthStatus = { setup_required: false, logged_in: false, username: null };

export function useAuth() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.authStatus(),
    queryFn: () => api.get<AuthStatus>("/api/auth/status"),
    staleTime: 60_000,
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  /** 执行一个认证动作；失败时不抛，把可读的原因放进 `error`。 */
  const run = useCallback(
    async (action: AuthAction, fn: () => Promise<unknown>, onDone?: () => Promise<unknown> | void) => {
      setPending(true);
      setError(null);
      try {
        await fn();
        await onDone?.();
      } catch (e) {
        setError(authErrorMessage(action, e));
      } finally {
        setPending(false);
      }
    },
    [],
  );

  const refreshStatus = () => client.refetchQueries({ queryKey: queryKeys.authStatus() });

  return {
    status: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
    error,
    pending,
    clearError: () => setError(null),
    login: (username: string, password: string) =>
      run("login", () => api.post("/api/auth/login", { username, password }), refreshStatus),
    setup: (username: string, password: string) =>
      run("setup", () => api.post("/api/auth/setup", { username, password }), refreshStatus),
    logout: () =>
      run("logout", () => api.post("/api/auth/logout"), () => {
        client.removeQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
        client.setQueryData(queryKeys.authStatus(), LOGGED_OUT);
      }),
    changePassword: (oldPassword: string, newPassword: string) =>
      run("changePassword", () =>
        api.post("/api/auth/password", { old_password: oldPassword, new_password: newPassword }),
      ),
  };
}

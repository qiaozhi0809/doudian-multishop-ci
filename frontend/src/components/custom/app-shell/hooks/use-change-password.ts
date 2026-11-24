import { useCallback, useState } from "react";
import { useAuth } from "@/pages/auth/hooks/use-auth";

/** 修改密码对话框的状态：开关、提交、成功与失败原因（就地显示）。 */
export function useChangePassword() {
  const auth = useAuth();
  const [open, setOpenState] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  const setOpen = useCallback(
    (next: boolean) => {
      setOpenState(next);
      setSucceeded(false);
      auth.clearError();
    },
    [auth],
  );

  const submit = useCallback(
    async (oldPassword: string, newPassword: string) => {
      setSucceeded(false);
      const ok = await auth.changePassword(oldPassword, newPassword);
      setSucceeded(ok);
      return ok;
    },
    [auth],
  );

  return { open, setOpen, submit, pending: auth.pending, error: auth.error, succeeded };
}

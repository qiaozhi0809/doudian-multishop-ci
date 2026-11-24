import { ApiError } from "@/lib/api-client";

export type AuthAction = "login" | "setup" | "changePassword" | "logout";

export const MIN_PASSWORD_LENGTH = 8;

export function validatePassword(password: string): string | null {
  return password.length < MIN_PASSWORD_LENGTH ? `密码至少 ${MIN_PASSWORD_LENGTH} 位` : null;
}

const FALLBACK: Record<AuthAction, string> = {
  login: "登录失败，请稍后重试",
  setup: "创建账号失败，请稍后重试",
  changePassword: "修改密码失败，请稍后重试",
  logout: "退出失败，请稍后重试",
};

/** 错误 = 发生了什么 + 怎么办（ui-guidelines 第 8 节）。 */
export function authErrorMessage(action: AuthAction, error: unknown): string {
  if (error instanceof ApiError) {
    if (error.type === "NetworkError") return error.message;
    if (action === "login" && error.status === 401) return "账号或密码错误";
    if (action === "login" && error.status === 423) return "尝试次数过多，请 5 分钟后再试";
    if (action === "setup" && error.status === 409) return "管理员已创建，请直接登录";
  }
  return FALLBACK[action];
}

import { ApiError } from "@/lib/api-client";

/** 阻断原因已经是中文句子，原样展示；空值不显示。 */
export const blockedText = (reason: string | null): string => reason ?? "";

/** 操作失败的可读文案（错误信封的 message 已由后端写好）。 */
export function actionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.type === "DecryptCooldown") {
      return "该店解密冷却中，约 3 小时后恢复；取号不受影响";
    }
    return error.message || "操作失败，请重试";
  }
  return "操作失败，请重试";
}

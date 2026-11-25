import { ApiError } from "@/lib/api-client";
import type { components } from "@/lib/api-types";

export type ShipCheck = components["schemas"]["ShipCheckResponse"];

/** 操作失败的可读文案（错误信封的 message 已由后端写好）。 */
export function actionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message || "操作失败，请重试";
  return "操作失败，请重试";
}

export function checkSummary(check: ShipCheck): string {
  const parts = [`${check.total_orders} 单通过检查`];
  if (check.double_check_total > 0) parts.push(`${check.double_check_total} 个二次确认项`);
  if (check.blocked.length > 0) parts.push(`${check.blocked.length} 单不可发货`);
  if (check.shop_errors.length > 0) parts.push(`${check.shop_errors.length} 家店检查失败`);
  return parts.join("；");
}

export function confirmLabel(check: ShipCheck): string {
  return check.double_check_total > 0 ? "按住确认发货（已核对二次确认项）" : "按住确认发货";
}

/** 发货前检查结果里需要人先看的提示（二次确认 / 保证金等）。 */
export function placeHolderText(placeHolder: Record<string, unknown> | null): string {
  if (!placeHolder) return "";
  const text = placeHolder.text;
  return typeof text === "string" ? text : "";
}

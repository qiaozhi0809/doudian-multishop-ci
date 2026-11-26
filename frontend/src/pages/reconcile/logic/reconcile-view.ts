import type { components } from "@/lib/api-types";
import { EMPTY_TEXT } from "@/lib/empty-text";

export type Finding = components["schemas"]["ReconcileFindingRow"];
export type ReconcileRun = components["schemas"]["ReconcileRunRow"];

export const PAGE_SIZE = 50;
/** 可排序的列，与后端 /api/reconcile/findings 的 sort 白名单一致；默认最新发现的在前。 */
export const FINDING_SORT_KEYS = ["shop_name", "kind", "created_at", "status"] as const;

export const KIND_OPTIONS = [
  { value: "all", label: "全部异常" },
  { value: "local_shipped_platform_not", label: "平台未发" },
  { value: "platform_shipped_local_not", label: "本地无记录" },
  { value: "waybill_mismatch", label: "运单不一致" },
] as const;

export type KindFilter = (typeof KIND_OPTIONS)[number]["value"];
export const isKind = (value: string | null): value is KindFilter =>
  KIND_OPTIONS.some((option) => option.value === value);

export const STATUS_OPTIONS = [
  { value: "all", label: "全部处理状态" },
  { value: "open", label: "未处理" },
  { value: "handled", label: "已处理" },
] as const;

export type StatusFilter = (typeof STATUS_OPTIONS)[number]["value"];
export const isStatus = (value: string | null): value is StatusFilter =>
  STATUS_OPTIONS.some((option) => option.value === value);

export type Tone = "success" | "info" | "warning" | "danger";

export function kindTone(kind: string): Tone {
  if (kind === "local_shipped_platform_not") return "danger";
  if (kind === "waybill_mismatch") return "warning";
  return "info";
}

export function trackingPair(row: Finding): string {
  return `${row.local_tracking_no ?? EMPTY_TEXT} → ${row.platform_tracking_no ?? EMPTY_TEXT}`;
}

export function runSummary(run: ReconcileRun): string {
  if (run.status === "running") return "检查进行中，结果会自动刷新";
  const head = run.status === "failed" ? "检查失败" : "检查完成";
  const tail = run.error ? `；${run.error}` : "";
  return `${head}：扫描 ${run.scanned} 单，发现 ${run.finding_count} 条异常${tail}`;
}

export function runTone(run: ReconcileRun): Tone {
  if (run.status === "running") return "info";
  if (run.status === "failed") return "danger";
  return "success";
}

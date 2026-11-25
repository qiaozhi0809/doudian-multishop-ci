import type { components } from "@/lib/api-types";

type OrderRow = components["schemas"]["OrderRow"];
export type LocalStatus = OrderRow["status"];

type Tone = "neutral" | "info" | "success" | "danger";

/** 本地状态（ui-guidelines 第 5 节）。订单页与打单台共用一套文案。 */
const LOCAL: Record<LocalStatus, { label: string; tone: Tone }> = {
  synced: { label: "待处理", tone: "neutral" },
  pending_label: { label: "待取号", tone: "neutral" },
  label_obtained: { label: "已取号", tone: "info" },
  printed: { label: "已打印", tone: "info" },
  shipped: { label: "已发货", tone: "success" },
  exception: { label: "异常", tone: "danger" },
  cancelled: { label: "已取消", tone: "neutral" },
  closed: { label: "已关闭", tone: "neutral" },
};

export const localStatusBadge = (status: LocalStatus) => LOCAL[status];

/** 本地状态筛选选项（对应 GET /api/orders?status=）。 */
export const LOCAL_STATUS_OPTIONS = (Object.keys(LOCAL) as LocalStatus[]).map((value) => ({
  value,
  label: LOCAL[value].label,
}));

export const isLocalStatus = (value: string | null): value is LocalStatus =>
  value !== null && value in LOCAL;

/** 平台状态：已确认的状态码给出文字，其余保留原始整数。 */
export function platformStatusText(code: number | null): string {
  if (code === null) return "暂无";
  const known: Record<number, string> = { 2: "待发货", 3: "已发货", 4: "已关闭", 5: "已完成" };
  return known[code] ?? `状态 ${code}`;
}

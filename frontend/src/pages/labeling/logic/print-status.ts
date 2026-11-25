import type { components } from "@/lib/api-types";

export type PrintJob = components["schemas"]["PrintJobRow"];
export type WaybillPrint = components["schemas"]["WaybillPrintRow"];
export type PrinterStatus = components["schemas"]["PrinterStatus"];

// 纯逻辑里用的窄类型：与接口模型一致，测试构造对象不需要全字段类型体操
export type PrintJobLike = PrintJob;
export type WaybillPrintLike = WaybillPrint;

export type JobTone = "neutral" | "success" | "warning" | "danger";

export interface PrintGateInput {
  stage: string;
  selectedCount: number;
  componentAvailable: boolean | null;
  busy: boolean;
}

/** 打印按钮的可用性：组件未启动时置灰并给出原因（flows 10 节强制约束）。 */
export function printGate(input: PrintGateInput): { disabled: boolean; reason: string | null } {
  if (input.stage !== "labeled") return { disabled: true, reason: "先打单，再到「待发货」里打印" };
  if (input.componentAvailable === null) {
    return { disabled: true, reason: "正在检测打印组件" };
  }
  if (!input.componentAvailable) {
    return { disabled: true, reason: "请先启动抖店官方打印组件" };
  }
  if (input.busy) return { disabled: true, reason: "有操作进行中" };
  if (input.selectedCount === 0) return { disabled: true, reason: "请先勾选面单" };
  return { disabled: false, reason: null };
}

/** 勾选的订单 → 它们的有效面单 id（打印接口按面单维度提交）。 */
export function selectedWaybillIds(
  selected: ReadonlySet<number>,
  rows: { id: number; waybill: { id: number } | null }[],
): number[] {
  return rows
    .filter((row) => selected.has(row.id) && row.waybill !== null)
    .map((row) => row.waybill!.id);
}

const COMPONENT_NOTICE =
  "抖店官方打印组件未启动，打印按钮已禁用。请启动打印组件（安装后常驻系统托盘）后重试";

export function componentNotice(status: PrinterStatus | undefined): string | null {
  if (!status || status.available) return null;
  return COMPONENT_NOTICE;
}

/** 面单最近一次打印任务的徽章；无打印数据单独提示「需手动补打」。 */
export function jobBadge(
  job: PrintJobLike | null | undefined,
): { label: string; tone: JobTone } | null {
  if (!job) return null;
  if (job.status === "queued") return { label: "打印中", tone: "neutral" };
  if (job.status === "success") return { label: "已打印", tone: "success" };
  if (job.result_code === "no_print_data") return { label: "需手动补打", tone: "warning" };
  return { label: "打印失败", tone: "danger" };
}

/** 一个打印批次的汇总文案（排队中显示剩余张数，结束显示三类结果）。 */
export function summarizePrint(rows: WaybillPrintLike[] | undefined): string | null {
  const jobs = (rows ?? [])
    .map((row) => row.job)
    .filter((job): job is PrintJobLike => job !== null && job !== undefined);
  if (jobs.length === 0) return null;
  const pending = jobs.filter((job) => job.status === "queued").length;
  if (pending > 0) return `打印中：剩余 ${pending} 张面单`;
  const ok = jobs.filter((job) => job.status === "success").length;
  const manual = jobs.filter(
    (job) => job.status === "failed" && job.result_code === "no_print_data",
  ).length;
  const failed = jobs.length - ok - manual;
  const parts = [`成功 ${ok}`];
  if (manual > 0) parts.push(`需手动补打 ${manual}`);
  if (failed > 0) parts.push(`失败 ${failed}`);
  return `打印结束：${parts.join("，")}`;
}

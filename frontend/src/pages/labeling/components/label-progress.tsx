import { Alert } from "@/components/arc/alert/alert";
import type { ProgressState } from "../logic/preview-summary";

/** 执行进度：按 SSE 逐单汇总；结束后给出成功 / 失败 / 待核实计数（结果就地反馈）。 */
export function LabelProgress({ progress }: { progress: ProgressState }) {
  if (Object.keys(progress.rows).length === 0) return null;
  const tone = progress.done
    ? progress.failed > 0 || progress.verifying > 0
      ? "warning"
      : "success"
    : "info";
  const title = progress.done
    ? `执行完成：成功 ${progress.ok}，失败 ${progress.failed}，待核实 ${progress.verifying}，跳过 ${progress.skipped}`
    : `执行中：成功 ${progress.ok}，失败 ${progress.failed}，待核实 ${progress.verifying}，跳过 ${progress.skipped}`;
  return <Alert tone={tone} title={title} />;
}

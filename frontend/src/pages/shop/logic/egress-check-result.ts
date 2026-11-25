import type { components } from "@/lib/api-types";

type EgressStatusOut = components["schemas"]["EgressStatusOut"];

export interface CheckResult {
  tone: "success" | "warning" | "danger" | "info";
  text: string;
}

/** 出口检查的结果提示（错误 = 发生了什么 + 怎么办）。 */
export function egressCheckResult(out: EgressStatusOut): CheckResult {
  switch (out.egress_status) {
    case "ok":
      return { tone: "success", text: `出口正常 · ${out.egress_ip ?? "暂无"}` };
    case "unreachable":
      return { tone: "danger", text: "出口不通，请检查代理是否到期或更换代理" };
    case "duplicate":
      return { tone: "danger", text: "出口 IP 与其他店重复，请更换出口" };
    case "changed":
      return {
        tone: "warning",
        text: out.egress_ip_pending ? `出口 IP 已变为 ${out.egress_ip_pending}，需确认` : "出口 IP 已变化，需确认",
      };
    default:
      return { tone: "info", text: "出口尚未检查" };
  }
}

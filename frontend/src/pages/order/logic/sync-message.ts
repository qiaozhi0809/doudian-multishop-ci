import type { components } from "@/lib/api-types";

type SyncStarted = components["schemas"]["SyncStarted"];

/** 手动同步的反馈：区分「已开始同步 N 家店」与「N 家店正在同步中」。 */
export function syncMessage(resp: SyncStarted): { tone: "success" | "info"; text: string } {
  const parts: string[] = [];
  if (resp.started.length) parts.push(`已开始同步 ${resp.started.length} 家店`);
  if (resp.already_running.length) parts.push(`${resp.already_running.length} 家店正在同步中`);
  if (!parts.length) return { tone: "info", text: "没有可同步的店铺" };
  return { tone: resp.started.length ? "success" : "info", text: parts.join("，") };
}

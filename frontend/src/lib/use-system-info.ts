import { useQuery } from "@tanstack/react-query";
import { api } from "./api-client";
import type { components } from "./api-types";
import { queryKeys } from "./query-keys";

export type SystemInfo = components["schemas"]["SystemInfo"];

/**
 * 系统信息（M7）：演练模式标识与版本号。
 * 读取失败按「正常模式」处理，不阻塞界面（例如后端尚未升级时）。
 */
export function useSystemInfo() {
  const query = useQuery({
    queryKey: queryKeys.systemInfo(),
    queryFn: () => api.get<SystemInfo>("/api/system/info"),
    staleTime: 60_000,
    retry: false,
  });
  return {
    dryRun: query.data?.dry_run === true,
    version: query.data?.version ?? null,
  };
}

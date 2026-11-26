import { useQuery } from "@tanstack/react-query";
import { api } from "./api-client";
import type { components } from "./api-types";
import { queryKeys } from "./query-keys";

export type PoolItem = components["schemas"]["PoolItem"];

/** 代理池列表：代理池页与店铺出口里的「从池选择」共用同一个查询与缓存。 */
export function usePoolItems() {
  return useQuery({ queryKey: queryKeys.proxyPool(), queryFn: () => api.get<PoolItem[]>("/api/proxy-pool") });
}

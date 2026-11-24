import { useQuery } from "@tanstack/react-query";
import { api } from "./api-client";
import type { components } from "./api-types";
import { queryKeys } from "./query-keys";

export type ShopRow = components["schemas"]["ShopRow"];

/** 店铺列表与会话健康（外壳的筛选器 / 健康指示与店铺页共用同一个查询）。 */
export function useShops() {
  return useQuery({ queryKey: queryKeys.shops(), queryFn: () => api.get<ShopRow[]>("/api/shops") });
}

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";

/** 某店的基础数据（只在抽屉打开、有店铺 id 时请求）。 */
export function useShopBase(shopId: number | null) {
  return useQuery({
    queryKey: queryKeys.shopBase(shopId ?? 0),
    queryFn: () => api.get<components["schemas"]["BaseData"]>(`/api/shops/${shopId}/base`),
    enabled: shopId !== null,
  });
}

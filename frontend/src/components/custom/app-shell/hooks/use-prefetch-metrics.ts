import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { prefetchMetrics } from "@/lib/metric-queries";

/** 一进外壳就把各页顶部指标卡的数取回来，第一次打开任何页面都不用等（1 分钟内不重复取）。 */
export function usePrefetchMetrics(shopIds: number[], hasShops: boolean) {
  const client = useQueryClient();
  useEffect(() => {
    if (hasShops) prefetchMetrics(client, shopIds);
  }, [client, hasShops, shopIds]);
}

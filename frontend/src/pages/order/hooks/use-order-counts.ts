import { useQuery } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { metricQueries } from "@/lib/metric-queries";
import { aggregateCounts } from "../logic/aggregate-counts";

/** 跨店 tab 计数（平台口径）：合计只含取到数据的店，取不到的店单独列出。 */
export function useOrderCounts() {
  const { shopIds } = useShopFilter();
  return useQuery({
    ...metricQueries.orderCounts(shopIds),
    select: aggregateCounts,
  });
}

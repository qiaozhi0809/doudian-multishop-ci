import { keepPreviousData, queryOptions, type QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";

type S = components["schemas"];

/**
 * 各页顶部指标卡的数据（仪表盘与各页共用同一份缓存）。
 * 其中售后、商品计数要现场去抖店取（1 ~ 3 秒），所以：
 * - 1 分钟内切页直接用缓存，不重取，也少打平台接口；
 * - 外壳一进来就预取，第一次打开任何页面都不用等；
 * - 换店铺范围时先显示上一份数字，取到再换，不闪骨架。
 */
const FRESH_MS = 60_000;

export const metricQueries = {
  orderCounts: (shopIds: number[]) =>
    queryOptions({
      queryKey: queryKeys.orderCounts(shopIds),
      queryFn: () => api.get<S["OrderCountsResponse"]>("/api/orders/counts", { shop_ids: shopIds }),
      staleTime: FRESH_MS,
      placeholderData: keepPreviousData,
    }),
  aftersaleCounts: (shopIds: number[]) =>
    queryOptions({
      queryKey: queryKeys.aftersaleCounts(shopIds),
      queryFn: () => api.get<S["AftersaleCountsResponse"]>("/api/aftersale/counts", { shop_ids: shopIds }),
      staleTime: FRESH_MS,
      placeholderData: keepPreviousData,
    }),
  productCounts: (shopIds: number[]) =>
    queryOptions({
      queryKey: queryKeys.productCounts(shopIds),
      queryFn: () => api.get<S["ProductCountsResponse"]>("/api/catalog/products/counts", { shop_ids: shopIds }),
      staleTime: FRESH_MS,
      placeholderData: keepPreviousData,
    }),
  stockSummary: (shopIds: number[]) =>
    queryOptions({
      queryKey: queryKeys.stockSummary(shopIds),
      queryFn: () => api.get<S["StockSummary"]>("/api/catalog/stock/summary", { shop_ids: shopIds }),
      staleTime: FRESH_MS,
      placeholderData: keepPreviousData,
    }),
  fundSummary: (shopIds: number[]) =>
    queryOptions({
      queryKey: queryKeys.fundSummary(shopIds),
      queryFn: () => api.get<S["FundSummary"]>("/api/fund/summary", { shop_ids: shopIds }),
      staleTime: FRESH_MS,
      placeholderData: keepPreviousData,
    }),
};

/** 预取全部指标（已有新鲜缓存的跳过）。 */
export function prefetchMetrics(client: QueryClient, shopIds: number[]) {
  void client.prefetchQuery(metricQueries.orderCounts(shopIds));
  void client.prefetchQuery(metricQueries.aftersaleCounts(shopIds));
  void client.prefetchQuery(metricQueries.productCounts(shopIds));
  void client.prefetchQuery(metricQueries.stockSummary(shopIds));
  void client.prefetchQuery(metricQueries.fundSummary(shopIds));
}

import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { metricQueries } from "@/lib/metric-queries";
import { queryKeys } from "@/lib/query-keys";
import { useListSort, useSettledSort } from "@/lib/use-list-sort";
import { useQuickFilter } from "@/lib/use-quick-filter";
import { useShops } from "@/lib/use-shops";
import { PAGE_SIZE, STOCK_QUICK_KEYS, STOCK_SORT_KEYS } from "../logic/stock-page";
import { useStockSync } from "./use-stock-sync";

type PageData = components["schemas"]["StockPage"];
type Warehouses = components["schemas"]["WarehousesResponse"];

/** 库存页数据：快捷筛选（预警 / 售罄）、排序与页码在 URL 里；预警汇总来自本地快照，仓库列表来自上游。 */
export function useStockPage() {
  const shops = useShops();
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();
  const sorting = useListSort(STOCK_SORT_KEYS);

  const quick = useQuickFilter(STOCK_QUICK_KEYS);
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const setPage = useCallback(
    (value: number) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value > 1) next.set("page", String(value));
        else next.delete("page");
        return next;
      }),
    [setParams],
  );

  const list = useQuery({
    queryKey: queryKeys.stock(shopIds, { page, ...sorting.query, ...quick.query }),
    queryFn: () =>
      api.get<PageData>("/api/catalog/stock", {
        shop_ids: shopIds, page, page_size: PAGE_SIZE, ...sorting.query, ...quick.query,
      }),
    placeholderData: keepPreviousData,
  });

  const summary = useQuery(metricQueries.stockSummary(shopIds));

  const warehouses = useQuery({
    queryKey: queryKeys.stockWarehouses(shopIds),
    queryFn: () => api.get<Warehouses>("/api/catalog/stock/warehouses", { shop_ids: shopIds }),
  });

  const sync = useStockSync();
  const names = useMemo(
    () => new Map((shops.data ?? []).map((s) => [s.id, s.name])),
    [shops.data],
  );

  const shownSort = useSettledSort(sorting.sort, !list.isPlaceholderData);
  return {
    shopsState: shops.isLoading
      ? ("loading" as const)
      : shops.isError
        ? ("error" as const)
        : (shops.data ?? []).length === 0
          ? ("empty" as const)
          : ("ready" as const),
    retryShops: () => void shops.refetch(),
    shopName: (id: number) => names.get(id) ?? `店铺 ${id}`,
    quick,
    page,
    setPage,
    sort: shownSort,
    setSort: sorting.setSort,
    list,
    summary,
    warehouses,
    sync,
  };
}

export type StockPageState = ReturnType<typeof useStockPage>;

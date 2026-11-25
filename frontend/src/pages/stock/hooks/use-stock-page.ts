import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useShops } from "@/lib/use-shops";
import { PAGE_SIZE, isStockView, type StockView } from "../logic/stock-page";
import { useStockSync } from "./use-stock-sync";

type PageData = components["schemas"]["StockPage"];
type Summary = components["schemas"]["StockSummary"];
type Warehouses = components["schemas"]["WarehousesResponse"];

/** 库存页数据：预警筛选与页码在 URL 里；预警汇总来自本地快照，仓库列表来自上游。 */
export function useStockPage() {
  const shops = useShops();
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();

  const rawView = params.get("view");
  const view: StockView = isStockView(rawView) ? rawView : "all";
  const alarmOnly = view === "alarm";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const setView = useCallback(
    (value: StockView) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value === "all") next.delete("view");
        else next.set("view", value);
        next.delete("page");
        return next;
      }),
    [setParams],
  );

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
    queryKey: queryKeys.stock(shopIds, { alarmOnly, page }),
    queryFn: () =>
      api.get<PageData>("/api/catalog/stock", {
        shop_ids: shopIds, alarm_only: alarmOnly, page, page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const summary = useQuery({
    queryKey: queryKeys.stockSummary(shopIds),
    queryFn: () => api.get<Summary>("/api/catalog/stock/summary", { shop_ids: shopIds }),
  });

  const warehouses = useQuery({
    queryKey: queryKeys.stockWarehouses(shopIds),
    queryFn: () => api.get<Warehouses>("/api/catalog/stock/warehouses", { shop_ids: shopIds }),
  });

  const sync = useStockSync();
  const names = useMemo(
    () => new Map((shops.data ?? []).map((s) => [s.id, s.name])),
    [shops.data],
  );

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
    view,
    setView,
    page,
    setPage,
    list,
    summary,
    warehouses,
    sync,
  };
}

export type StockPageState = ReturnType<typeof useStockPage>;

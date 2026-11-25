import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { metricQueries } from "@/lib/metric-queries";
import { queryKeys } from "@/lib/query-keys";
import { useShops } from "@/lib/use-shops";
import { PAGE_SIZE } from "../logic/catalog-page";
import { useCatalogSync } from "./use-catalog-sync";

type PageData = components["schemas"]["ProductPage"];
type GroupsResponse = components["schemas"]["ProductGroupsResponse"];

/** 商品页数据：关键字与页码在 URL 里；计数与分组来自上游（每店一请求，失败隔离）。 */
export function useCatalogPage() {
  const shops = useShops();
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();

  const keyword = params.get("q") ?? "";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const setKeyword = useCallback(
    (value: string) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value.trim()) next.set("q", value);
        else next.delete("q");
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
    queryKey: queryKeys.products(shopIds, { keyword: keyword || undefined, page }),
    queryFn: () =>
      api.get<PageData>("/api/catalog/products", {
        shop_ids: shopIds, keyword: keyword || undefined, page, page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const counts = useQuery(metricQueries.productCounts(shopIds));

  const groups = useQuery({
    queryKey: queryKeys.productGroups(shopIds),
    queryFn: () => api.get<GroupsResponse>("/api/catalog/products/groups", { shop_ids: shopIds }),
  });

  const sync = useCatalogSync();
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
    keyword,
    setKeyword,
    page,
    setPage,
    list,
    counts,
    groups,
    sync,
  };
}

export type CatalogPageState = ReturnType<typeof useCatalogPage>;

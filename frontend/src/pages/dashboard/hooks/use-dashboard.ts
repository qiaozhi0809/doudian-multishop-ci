import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useShops, type ShopRow } from "@/lib/use-shops";
import {
  buildDashboard,
  type AftersaleCountsResponse,
  type DashboardModel,
  type FundSummary,
  type OrderCountsResponse,
  type ProductCountsResponse,
  type StockSummary,
} from "../logic/dashboard";

export interface SectionState {
  state: "loading" | "error" | "ready";
  retry: () => void;
}

export interface DashboardPage {
  shopsState: "loading" | "error" | "empty" | "ready";
  retryShops: () => void;
  shopName: (id: number) => string;
  model: DashboardModel;
  sections: {
    orderCounts: SectionState;
    aftersale: SectionState;
    fund: SectionState;
    stock: SectionState;
    products: SectionState;
  };
}

const NO_SHOPS: ShopRow[] = [];

/** 仪表盘数据：全部复用已有只读聚合接口；同一 query key 与各页面共享缓存。 */
export function useDashboardPage(): DashboardPage {
  const { shopIds } = useShopFilter();
  const shopsQuery = useShops();
  const shops = shopsQuery.data ?? NO_SHOPS;

  const orderCounts = useQuery({
    queryKey: queryKeys.orderCounts(shopIds),
    queryFn: () => api.get<OrderCountsResponse>("/api/orders/counts", { shop_ids: shopIds }),
    enabled: shops.length > 0,
  });
  const aftersale = useQuery({
    queryKey: queryKeys.aftersaleCounts(shopIds),
    queryFn: () => api.get<AftersaleCountsResponse>("/api/aftersale/counts", { shop_ids: shopIds }),
    enabled: shops.length > 0,
  });
  const fund = useQuery({
    queryKey: queryKeys.fundSummary(shopIds),
    queryFn: () => api.get<FundSummary>("/api/fund/summary", { shop_ids: shopIds }),
    enabled: shops.length > 0,
  });
  const stock = useQuery({
    queryKey: queryKeys.stockSummary(shopIds),
    queryFn: () => api.get<StockSummary>("/api/catalog/stock/summary", { shop_ids: shopIds }),
    enabled: shops.length > 0,
  });
  const products = useQuery({
    queryKey: queryKeys.productCounts(shopIds),
    queryFn: () => api.get<ProductCountsResponse>("/api/catalog/products/counts", { shop_ids: shopIds }),
    enabled: shops.length > 0,
  });

  const model = useMemo(
    () =>
      buildDashboard({
        shops,
        orderCounts: orderCounts.data,
        aftersaleCounts: aftersale.data,
        fund: fund.data,
        stock: stock.data,
        products: products.data,
      }),
    [shops, orderCounts.data, aftersale.data, fund.data, stock.data, products.data],
  );

  const shopName = useCallback(
    (id: number) => shops.find((shop) => shop.id === id)?.name ?? `店铺 ${id}`,
    [shops],
  );

  const section = (query: { isLoading: boolean; isError: boolean; refetch: () => Promise<unknown> }): SectionState => ({
    state: query.isLoading ? "loading" : query.isError ? "error" : "ready",
    retry: () => void query.refetch(),
  });

  const shopsState = shopsQuery.isLoading
    ? "loading"
    : shopsQuery.isError
      ? "error"
      : shops.length === 0
        ? "empty"
        : "ready";

  return {
    shopsState,
    retryShops: () => void shopsQuery.refetch(),
    shopName,
    model,
    sections: {
      orderCounts: section(orderCounts),
      aftersale: section(aftersale),
      fund: section(fund),
      stock: section(stock),
      products: section(products),
    },
  };
}

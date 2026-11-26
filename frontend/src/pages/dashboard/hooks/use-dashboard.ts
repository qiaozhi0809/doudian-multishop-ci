import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { metricQueries } from "@/lib/metric-queries";
import { useShops, type ShopRow } from "@/lib/use-shops";
import { useShopsWithOpenProblems } from "@/lib/use-shops-with-open-problems";
import { buildDashboard, type DashboardModel } from "../logic/dashboard";

export interface SectionState {
  state: "loading" | "error" | "ready";
  retry: () => void;
}

export interface DashboardPage {
  shopsState: "loading" | "error" | "empty" | "ready";
  retryShops: () => void;
  shopName: (id: number) => string;
  /** 顶部横条里已列出（登录 / 出口 / 风控）的店：未取到提示不再重复 */
  bannerShopIds: ReadonlySet<number>;
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
  const bannerShopIds = useShopsWithOpenProblems();
  const shops = shopsQuery.data ?? NO_SHOPS;

  const enabled = shops.length > 0;
  const orderCounts = useQuery({ ...metricQueries.orderCounts(shopIds), enabled });
  const aftersale = useQuery({ ...metricQueries.aftersaleCounts(shopIds), enabled });
  const fund = useQuery({ ...metricQueries.fundSummary(shopIds), enabled });
  const stock = useQuery({ ...metricQueries.stockSummary(shopIds), enabled });
  const products = useQuery({ ...metricQueries.productCounts(shopIds), enabled });

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
    bannerShopIds,
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

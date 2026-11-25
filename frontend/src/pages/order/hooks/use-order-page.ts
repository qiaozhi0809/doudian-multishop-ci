import { useShops } from "@/lib/use-shops";
import { useOrderCounts } from "./use-order-counts";
import { useOrderSync } from "./use-order-sync";
import { useOrders } from "./use-orders";

/** 订单页的全部数据：店铺、订单列表、计数、同步。 */
export function useOrderPage() {
  const shops = useShops();
  const orders = useOrders();
  const counts = useOrderCounts();
  const sync = useOrderSync();
  const names = new Map((shops.data ?? []).map((s) => [s.id, s.name]));

  return {
    shopsState: shops.isLoading ? ("loading" as const) : shops.isError ? ("error" as const) : (shops.data ?? []).length === 0 ? ("empty" as const) : ("ready" as const),
    retryShops: () => void shops.refetch(),
    shopName: (id: number) => names.get(id) ?? `店铺 ${id}`,
    orders,
    counts,
    sync,
  };
}

export type OrderPage = ReturnType<typeof useOrderPage>;

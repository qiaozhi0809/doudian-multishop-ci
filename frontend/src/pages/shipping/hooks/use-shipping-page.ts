import { useMemo } from "react";
import { useShops } from "@/lib/use-shops";
import { selectedPackages } from "../logic/ship-columns";
import { useShippingActions } from "./use-shipping-actions";
import { useShippingPool } from "./use-shipping-pool";

/** 发货台的全部数据：店铺、待发货池与检查 / 发货动作。 */
export function useShippingPage() {
  const shops = useShops();
  const pool = useShippingPool();
  const actions = useShippingActions();
  const packageCount = useMemo(
    () => selectedPackages(pool.selected, pool.rows),
    [pool.selected, pool.rows],
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
    pool,
    actions,
    packageCount,
  };
}

export type ShippingPage = ReturnType<typeof useShippingPage>;

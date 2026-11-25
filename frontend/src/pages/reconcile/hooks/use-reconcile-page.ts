import { useShops } from "@/lib/use-shops";
import { useReconcile } from "./use-reconcile";

/** 对账页：店铺就绪 + 对账查询与动作。 */
export function useReconcilePage() {
  const shops = useShops();
  const reconcile = useReconcile();
  return {
    shopsState: shops.isLoading
      ? ("loading" as const)
      : shops.isError
        ? ("error" as const)
        : (shops.data ?? []).length === 0
          ? ("empty" as const)
          : ("ready" as const),
    retryShops: () => void shops.refetch(),
    reconcile,
  };
}

export type ReconcilePageState = ReturnType<typeof useReconcilePage>;

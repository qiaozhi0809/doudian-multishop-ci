import { useShops } from "@/lib/use-shops";
import { useLabelActions } from "./use-label-actions";
import { useLabelPool } from "./use-label-pool";
import { useReceiver } from "./use-receiver";

/** 打单台的全部数据：店铺、订单池、两步提交与收件人。 */
export function useLabelPage() {
  const shops = useShops();
  const pool = useLabelPool();
  const actions = useLabelActions();
  const receiver = useReceiver();

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
    receiver,
  };
}

export type LabelPage = ReturnType<typeof useLabelPage>;

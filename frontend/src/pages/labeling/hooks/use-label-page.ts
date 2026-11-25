import { useMemo } from "react";
import { useShops } from "@/lib/use-shops";
import { useShippingActions } from "./use-ship-actions";
import { useLabelActions } from "./use-label-actions";
import { useLabelPool } from "./use-label-pool";
import { usePrint } from "./use-print";
import { useReceiver } from "./use-receiver";

/** 打单发货页的全部数据：店铺、订单池、打单两步提交、打印、收件人，以及「待发货」里的发货。 */
export function useLabelPage() {
  const shops = useShops();
  const pool = useLabelPool();
  const actions = useLabelActions();
  const ship = useShippingActions();
  const receiver = useReceiver();
  const waybillIds = useMemo(
    () => pool.rows.flatMap((row) => (row.waybill ? [row.waybill.id] : [])),
    [pool.rows],
  );
  const print = usePrint(waybillIds);

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
    print,
    ship,
  };
}

export type LabelPage = ReturnType<typeof useLabelPage>;

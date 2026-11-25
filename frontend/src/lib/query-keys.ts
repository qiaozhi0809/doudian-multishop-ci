export interface OrderFilters {
  status?: string;
  page?: number;
}

export interface LabelPoolFilters {
  stage: string;
  page?: number;
}

/** 查询 key 统一在此定义；带店铺筛选条件。`*Root()` 用于前缀失效。 */
export const queryKeys = {
  authStatus: () => ["auth", "status"] as const,
  shops: () => ["shops"] as const,
  shopBase: (id: number) => ["shops", id, "base"] as const,
  ordersRoot: () => ["orders"] as const,
  orders: (shopIds: number[], filters: OrderFilters) => ["orders", shopIds, filters] as const,
  orderCountsRoot: () => ["orderCounts"] as const,
  orderCounts: (shopIds: number[]) => ["orderCounts", shopIds] as const,
  labelPoolRoot: () => ["labelPool"] as const,
  labelPool: (shopIds: number[], filters: LabelPoolFilters) =>
    ["labelPool", shopIds, filters] as const,
  printStatus: () => ["printStatus"] as const,
  printWaybillsRoot: () => ["printWaybills"] as const,
  printWaybills: (waybillIds: number[]) => ["printWaybills", waybillIds] as const,
};

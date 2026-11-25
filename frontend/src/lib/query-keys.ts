export interface OrderFilters {
  status?: string;
  page?: number;
}

export interface LabelPoolFilters {
  stage: string;
  page?: number;
}

export interface AftersaleFilters {
  view: "todo" | "all";
  status?: number;
  page: number;
}

export interface ProductFilters {
  keyword?: string;
  page: number;
}

export interface PageFilter {
  page: number;
}

export interface ReconcileFilters {
  kind: string;
  status: string;
  page: number;
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
  // ---- M5 只读聚合 ----
  aftersaleRoot: () => ["aftersale"] as const,
  aftersaleList: (shopIds: number[], filters: AftersaleFilters) =>
    ["aftersale", "list", shopIds, filters] as const,
  aftersaleStatuses: (shopIds: number[]) => ["aftersale", "statuses", shopIds] as const,
  aftersaleCounts: (shopIds: number[]) => ["aftersale", "counts", shopIds] as const,
  productsRoot: () => ["products"] as const,
  products: (shopIds: number[], filters: ProductFilters) =>
    ["products", "list", shopIds, filters] as const,
  productCounts: (shopIds: number[]) => ["products", "counts", shopIds] as const,
  productGroups: (shopIds: number[]) => ["products", "groups", shopIds] as const,
  stockRoot: () => ["stock"] as const,
  stock: (shopIds: number[], filters: PageFilter & { alarmOnly: boolean }) =>
    ["stock", "list", shopIds, filters] as const,
  stockSummary: (shopIds: number[]) => ["stock", "summary", shopIds] as const,
  stockWarehouses: (shopIds: number[]) => ["stock", "warehouses", shopIds] as const,
  fundRoot: () => ["fund"] as const,
  fundSummary: (shopIds: number[]) => ["fund", "summary", shopIds] as const,
  fundUnsettled: (shopIds: number[], page: number) =>
    ["fund", "unsettled", shopIds, page] as const,
  fundMargin: (shopIds: number[]) => ["fund", "margin", shopIds] as const,
  fundBills: (shopIds: number[], days: number) => ["fund", "bills", shopIds, days] as const,
  // ---- M3 打印 ----
  printStatus: () => ["printStatus"] as const,
  printWaybillsRoot: () => ["printWaybills"] as const,
  printWaybills: (waybillIds: number[]) => ["printWaybills", waybillIds] as const,
  // ---- M4 发货 / 对账 ----
  shippingPoolRoot: () => ["shippingPool"] as const,
  shippingPool: (shopIds: number[], page: number) =>
    ["shippingPool", shopIds, { page }] as const,
  reconcileRoot: () => ["reconcile"] as const,
  reconcileFindings: (shopIds: number[], filters: ReconcileFilters) =>
    ["reconcile", "findings", shopIds, filters] as const,
};

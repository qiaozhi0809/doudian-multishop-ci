export interface NavItem {
  path: string;
  label: string;
  icon:
    | "orders"
    | "labeling"
    | "shipping"
    | "reconcile"
    | "aftersale"
    | "products"
    | "stock"
    | "fund"
    | "shops";
}

/** 其他页面在后续里程碑加入。 */
export const NAV_ITEMS: NavItem[] = [
  { path: "/orders", label: "订单", icon: "orders" },
  { path: "/labeling", label: "打单台", icon: "labeling" },
  { path: "/shipping", label: "发货台", icon: "shipping" },
  { path: "/reconcile", label: "对账", icon: "reconcile" },
  { path: "/aftersale", label: "售后", icon: "aftersale" },
  { path: "/catalog", label: "商品", icon: "products" },
  { path: "/stock", label: "库存", icon: "stock" },
  { path: "/fund", label: "资金", icon: "fund" },
  { path: "/shops", label: "店铺与设置", icon: "shops" },
];

export function pageTitle(pathname: string): string {
  return NAV_ITEMS.find((i) => pathname === i.path || pathname.startsWith(`${i.path}/`))?.label ?? "";
}

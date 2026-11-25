export type NavIcon =
  | "dashboard"
  | "orders"
  | "labeling"
  | "reconcile"
  | "aftersale"
  | "products"
  | "stock"
  | "fund"
  | "shops";

export interface NavItem {
  path: string;
  label: string;
  icon: NavIcon;
}

/**
 * 一级导航按工作流分组（frontend.md 1.1）。
 * `link` 是不可折叠的独立入口；`group` 有组标题、可折叠。
 */
export type NavSection =
  | { kind: "link"; item: NavItem }
  | { kind: "group"; id: string; label: string; icon: NavIcon; items: NavItem[] };

export const NAV_SECTIONS: NavSection[] = [
  { kind: "link", item: { path: "/dashboard", label: "概览", icon: "dashboard" } },
  {
    kind: "group",
    id: "orders",
    label: "订单",
    icon: "orders",
    items: [
      { path: "/orders", label: "全部订单", icon: "orders" },
      { path: "/labeling", label: "打单发货", icon: "labeling" },
      { path: "/aftersale", label: "售后处理", icon: "aftersale" },
      { path: "/reconcile", label: "发货异常", icon: "reconcile" },
    ],
  },
  {
    kind: "group",
    id: "catalog",
    label: "商品",
    icon: "products",
    items: [
      { path: "/catalog", label: "商品列表", icon: "products" },
      { path: "/stock", label: "库存", icon: "stock" },
    ],
  },
  {
    kind: "group",
    id: "finance",
    label: "资金",
    icon: "fund",
    items: [
      { path: "/fund", label: "结算与保证金", icon: "fund" },
    ],
  },
];

/** 底部低频入口（侧栏里在「设置」组下）。 */
export const FOOTER_NAV: NavItem[] = [{ path: "/shops", label: "店铺管理", icon: "shops" }];

/** 全部可跳转项（含底部入口），按显示顺序。 */
export const NAV_ITEMS: NavItem[] = [
  ...NAV_SECTIONS.flatMap((section) => (section.kind === "link" ? [section.item] : section.items)),
  ...FOOTER_NAV,
];

const matches = (pathname: string, path: string): boolean =>
  pathname === path || pathname.startsWith(`${path}/`);

/** 页面标题：取路径匹配最长的一项（如 /shops/1 → 店铺管理）。 */
export function pageTitle(pathname: string): string {
  let best: NavItem | null = null;
  for (const item of NAV_ITEMS) {
    if (matches(pathname, item.path) && (!best || item.path.length > best.path.length)) {
      best = item;
    }
  }
  return best?.label ?? "";
}

export type NavIcon =
  | "dashboard"
  | "orders"
  | "labeling"
  | "shipping"
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
  { kind: "link", item: { path: "/dashboard", label: "仪表盘", icon: "dashboard" } },
  {
    kind: "group",
    id: "orders",
    label: "订单处理",
    icon: "orders",
    items: [
      { path: "/orders", label: "订单", icon: "orders" },
      { path: "/labeling", label: "打单台", icon: "labeling" },
      { path: "/shipping", label: "发货台", icon: "shipping" },
    ],
  },
  {
    kind: "group",
    id: "aftersale",
    label: "售后",
    icon: "aftersale",
    items: [{ path: "/aftersale", label: "售后工作台", icon: "aftersale" }],
  },
  {
    kind: "group",
    id: "catalog",
    label: "商品与库存",
    icon: "products",
    items: [
      { path: "/catalog", label: "商品", icon: "products" },
      { path: "/stock", label: "库存", icon: "stock" },
    ],
  },
  {
    kind: "group",
    id: "finance",
    label: "财务",
    icon: "fund",
    items: [
      { path: "/fund", label: "资金", icon: "fund" },
      { path: "/reconcile", label: "对账", icon: "reconcile" },
    ],
  },
];

/** 底部低频入口，与上方分组用分隔线隔开。 */
export const FOOTER_NAV: NavItem[] = [{ path: "/shops", label: "店铺与设置", icon: "shops" }];

/** 全部可跳转项（含底部入口），按显示顺序。 */
export const NAV_ITEMS: NavItem[] = [
  ...NAV_SECTIONS.flatMap((section) => (section.kind === "link" ? [section.item] : section.items)),
  ...FOOTER_NAV,
];

const matches = (pathname: string, path: string): boolean =>
  pathname === path || pathname.startsWith(`${path}/`);

/** 顶栏页面标题：取路径匹配最长的一项（如 /shops/1 → 店铺与设置）。 */
export function pageTitle(pathname: string): string {
  let best: NavItem | null = null;
  for (const item of NAV_ITEMS) {
    if (matches(pathname, item.path) && (!best || item.path.length > best.path.length)) {
      best = item;
    }
  }
  return best?.label ?? "";
}

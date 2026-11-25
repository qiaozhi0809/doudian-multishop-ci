import { Boxes, ClipboardList, LifeBuoy, Package, PanelLeftClose, PanelLeftOpen, Store, Truck, Wallet } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Button } from "@/components/arc/button/button";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { NAV_ITEMS, type NavItem } from "../logic/nav-items";
import { withShopFilter } from "../logic/shop-filter";
import styles from "../app-shell.module.css";

<<<<<<< HEAD
const ICONS = { orders: ClipboardList, labeling: Truck, shops: Store } as const;
=======
const ICONS = {
  orders: ClipboardList, aftersale: LifeBuoy, products: Package, stock: Boxes, fund: Wallet, shops: Store,
} as const;
>>>>>>> ac3d7cc (feat(frontend): 售后 / 商品 / 库存 / 资金四个聚合页)

interface SideNavProps {
  collapsed: boolean;
  onToggle: () => void;
  shopIds: number[];
}

function NavEntry({ item, collapsed, shopIds }: { item: NavItem; collapsed: boolean; shopIds: number[] }) {
  const Icon = ICONS[item.icon];
  const link = (
    <NavLink to={withShopFilter(item.path, shopIds)} className={styles.navLink} aria-label={collapsed ? item.label : undefined}>
      <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
      {!collapsed && <span className={styles.navLinkLabel}>{item.label}</span>}
    </NavLink>
  );
  return collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

export function SideNav({ collapsed, onToggle, shopIds }: SideNavProps) {
  return (
    <aside className={styles.sideNav} data-collapsed={collapsed}>
      <div className={styles.brand}>
        {!collapsed && <span>抖店管理</span>}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
          aria-expanded={!collapsed}
        >
          {collapsed ? (
            <PanelLeftOpen size={20} strokeWidth={1.75} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={20} strokeWidth={1.75} aria-hidden="true" />
          )}
        </Button>
      </div>
      <nav aria-label="主导航" className={styles.navList}>
        {NAV_ITEMS.map((item) => (
          <NavEntry key={item.path} item={item} collapsed={collapsed} shopIds={shopIds} />
        ))}
      </nav>
    </aside>
  );
}

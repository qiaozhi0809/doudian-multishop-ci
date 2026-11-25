import type { ReactNode } from "react";
import {
  Boxes,
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  Package,
  PackageCheck,
  Scale,
  Store,
  Truck,
  Wallet,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { FOOTER_NAV, NAV_SECTIONS, type NavItem } from "../logic/nav-items";
import { withShopFilter } from "../logic/shop-filter";
import styles from "../app-shell.module.css";

const ICONS = {
  dashboard: LayoutDashboard,
  orders: ClipboardList,
  labeling: Truck,
  shipping: PackageCheck,
  reconcile: Scale,
  aftersale: LifeBuoy,
  products: Package,
  stock: Boxes,
  fund: Wallet,
  shops: Store,
} as const;

function NavEntry({ item, shopIds }: { item: NavItem; shopIds: number[] }) {
  const Icon = ICONS[item.icon];
  return (
    <NavLink to={withShopFilter(item.path, shopIds)} className={styles.navLink}>
      <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
      <span className={styles.navLinkLabel}>{item.label}</span>
    </NavLink>
  );
}

interface SideNavProps {
  shopIds: number[];
  /** 品牌下方的全局店铺范围。 */
  scope: ReactNode;
  /** 个人中心上方的任务中心入口。 */
  tasks: ReactNode;
  account: ReactNode;
}

/** 浮动侧栏：品牌 → 店铺范围 → 分组导航（灰色组名，组内常显）→ 任务中心 → 左下角账号菜单。 */
export function SideNav({ shopIds, scope, tasks, account }: SideNavProps) {
  return (
    <aside className={styles.sideNav}>
      <div className={styles.brand}>抖店管理</div>
      <div className={styles.scopeSlot}>{scope}</div>
      <nav aria-label="主导航" className={styles.nav}>
        {NAV_SECTIONS.map((section) =>
          section.kind === "link" ? (
            <NavEntry key={section.item.path} item={section.item} shopIds={shopIds} />
          ) : (
            <div key={section.id} className={styles.navSection} role="group" aria-labelledby={`nav-group-${section.id}`}>
              <div id={`nav-group-${section.id}`} className={styles.navGroupTitle}>
                {section.label}
              </div>
              {section.items.map((item) => (
                <NavEntry key={item.path} item={item} shopIds={shopIds} />
              ))}
            </div>
          ),
        )}
        <div className={styles.navSection}>
          <div className={styles.navGroupTitle}>设置</div>
          {FOOTER_NAV.map((item) => (
            <NavEntry key={item.path} item={item} shopIds={shopIds} />
          ))}
        </div>
      </nav>
      <div className={styles.sideFoot}>
        {tasks}
        {account}
      </div>
    </aside>
  );
}

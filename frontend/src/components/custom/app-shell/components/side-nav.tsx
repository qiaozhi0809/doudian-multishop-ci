import {
  Boxes,
  ChevronDown,
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  Package,
  PackageCheck,
  PanelLeftClose,
  PanelLeftOpen,
  Scale,
  Store,
  Truck,
  Wallet,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { Button } from "@/components/arc/button/button";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import { activeSectionId, FOOTER_NAV, NAV_SECTIONS, type NavItem, type NavSection } from "../logic/nav-items";
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

interface SideNavProps {
  collapsed: boolean;
  onToggle: () => void;
  shopIds: number[];
  collapsedGroups: ReadonlySet<string>;
  onToggleGroup: (id: string) => void;
}

function NavEntry({ item, collapsed, shopIds }: { item: NavItem; collapsed: boolean; shopIds: number[] }) {
  const Icon = ICONS[item.icon];
  const link = (
    <NavLink to={withShopFilter(item.path, shopIds)} className={styles.navLink}>
      <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
      <span className={styles.navLinkLabel}>{item.label}</span>
    </NavLink>
  );
  return collapsed ? <Tooltip content={item.label} side="right">{link}</Tooltip> : link;
}

function GroupHeader({
  section,
  open,
  active,
  onToggle,
}: {
  section: Extract<NavSection, { kind: "group" }>;
  open: boolean;
  active: boolean;
  onToggle: () => void;
}) {
  const Icon = ICONS[section.icon];
  return (
    <button
      type="button"
      className={styles.groupHeader}
      data-active={active || undefined}
      aria-expanded={open}
      aria-controls={`nav-group-${section.id}`}
      onClick={onToggle}
    >
      <Icon size={20} strokeWidth={1.75} aria-hidden="true" />
      <span className={styles.groupLabel}>{section.label}</span>
      <ChevronDown size={16} strokeWidth={1.75} aria-hidden="true" className={styles.chevron} data-open={open || undefined} />
    </button>
  );
}

export function SideNav({ collapsed, onToggle, shopIds, collapsedGroups, onToggleGroup }: SideNavProps) {
  const { pathname } = useLocation();
  const current = activeSectionId(pathname);
  return (
    <aside className={styles.sideNav} data-collapsed={collapsed}>
      <div className={styles.brand}>
        <span className={styles.brandText}>抖店管理</span>
        <Button
          variant="ghost"
          size="sm"
          className={styles.brandToggle}
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
        <div className={styles.navSections}>
          {NAV_SECTIONS.map((section) => {
            if (section.kind === "link") {
              return <NavEntry key={section.item.path} item={section.item} collapsed={collapsed} shopIds={shopIds} />;
            }
            const open = !collapsedGroups.has(section.id);
            return (
              <div key={section.id} className={styles.navGroup}>
                <GroupHeader
                  section={section}
                  open={open}
                  active={current === section.id}
                  onToggle={() => onToggleGroup(section.id)}
                />
                <div id={`nav-group-${section.id}`} className={styles.groupItems} hidden={!open}>
                  {section.items.map((item) => (
                    <NavEntry key={item.path} item={item} collapsed={collapsed} shopIds={shopIds} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <div className={styles.navFooter}>
          {FOOTER_NAV.map((item) => (
            <NavEntry key={item.path} item={item} collapsed={collapsed} shopIds={shopIds} />
          ))}
        </div>
      </nav>
    </aside>
  );
}

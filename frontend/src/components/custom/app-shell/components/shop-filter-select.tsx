import * as Menu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronsUpDown, Store } from "lucide-react";
import menuStyles from "@/components/arc/dropdown-menu/dropdown-menu.module.css";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../app-shell.module.css";

interface ShopFilterSelectProps {
  shops: ShopRow[];
  shopIds: number[];
  disabled: boolean;
  onChange: (ids: number[]) => void;
}

function scopeText(shops: ShopRow[], ids: number[]): string {
  if (ids.length === 0) return "全部店铺";
  if (ids.length === 1) return shops.find((s) => s.id === ids[0])?.name ?? "1 家店铺";
  return `${ids.length} 家店铺`;
}

/** 侧栏顶部的全局店铺范围（多选，空 = 全部店铺）：对所有页面生效，勾选时菜单不关。 */
export function ShopFilterSelect({ shops, shopIds, disabled, onChange }: ShopFilterSelectProps) {
  const known = new Set(shops.map((s) => s.id));
  const selected = shopIds.filter((id) => known.has(id));
  const text = scopeText(shops, selected);
  const toggle = (id: number) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  return (
    <Menu.Root>
      <Menu.Trigger className={styles.scope} disabled={disabled} aria-label={`店铺筛选，${text}`}>
        <Store size={16} strokeWidth={1.75} aria-hidden="true" />
        <span className={styles.scopeText}>{text}</span>
        <ChevronsUpDown size={14} aria-hidden="true" className={styles.scopeChevron} />
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Content
          className={`${menuStyles.content} ${styles.scopeMenu}`}
          align="start"
          sideOffset={6}
          collisionPadding={12}
        >
          <Menu.CheckboxItem
            className={`${menuStyles.item} ${styles.scopeItem}`}
            checked={selected.length === 0}
            onSelect={(event) => {
              event.preventDefault();
              onChange([]);
            }}
          >
            <span className={styles.scopeCheck} aria-hidden="true">
              <Menu.ItemIndicator>
                <Check size={14} strokeWidth={2} />
              </Menu.ItemIndicator>
            </span>
            全部店铺
          </Menu.CheckboxItem>
          {shops.length > 0 && <Menu.Separator className={menuStyles.separator} />}
          {shops.map((shop) => (
            <Menu.CheckboxItem
              key={shop.id}
              className={`${menuStyles.item} ${styles.scopeItem}`}
              checked={selected.includes(shop.id)}
              onSelect={(event) => {
                event.preventDefault();
                toggle(shop.id);
              }}
            >
              <span className={styles.scopeCheck} aria-hidden="true">
                <Menu.ItemIndicator>
                  <Check size={14} strokeWidth={2} />
                </Menu.ItemIndicator>
              </span>
              {shop.name}
            </Menu.CheckboxItem>
          ))}
        </Menu.Content>
      </Menu.Portal>
    </Menu.Root>
  );
}

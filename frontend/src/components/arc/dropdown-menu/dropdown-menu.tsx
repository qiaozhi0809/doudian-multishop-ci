"use client";

import { Fragment, useRef } from "react";
import type { ReactNode } from "react";
import * as Menu from "@radix-ui/react-dropdown-menu";
import styles from "./dropdown-menu.module.css";

export interface DropdownItem {
  /** 同一菜单内要唯一，兼作 key。 */
  label: string;
  onSelect?: () => void;
  disabled?: boolean;
  icon?: ReactNode;
  /** 危险项：红色，放最后。 */
  destructive?: boolean;
  separatorBefore?: boolean;
}

export interface DropdownMenuProps {
  /** 触发元素，必须是能接 ref 的单个元素（按钮）。 */
  trigger: ReactNode;
  items: DropdownItem[];
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
}

/** 一个锚在触发元素上的操作列表。数据驱动：菜单项用 items 数组给。 */
export function DropdownMenu({ trigger, items, align = "end", side = "bottom" }: DropdownMenuProps) {
  // 用鼠标关菜单时不把焦点还给触发按钮：还回去会让按钮上的悬停提示（如「更多操作」）自己弹出来停着。
  // 用键盘关时照常还焦点，键盘用户不丢位置。
  const byPointer = useRef(false);
  return <Menu.Root>
    <Menu.Trigger asChild>{trigger}</Menu.Trigger>
    <Menu.Portal>
      <Menu.Content className={styles.content} align={align} side={side} sideOffset={6} collisionPadding={12}
        onPointerDown={() => { byPointer.current = true; }}
        onPointerDownOutside={() => { byPointer.current = true; }}
        onKeyDown={() => { byPointer.current = false; }}
        onCloseAutoFocus={event => { if (byPointer.current) event.preventDefault(); byPointer.current = false; }}>
        {items.map(item => <Fragment key={item.label}>
          {item.separatorBefore ? <Menu.Separator className={styles.separator} /> : null}
          <Menu.Item className={`${styles.item} ${item.destructive ? styles.destructive : ""}`} disabled={item.disabled} onSelect={() => item.onSelect?.()}>
            {item.icon ? <span aria-hidden="true" style={{ display: "inline-flex" }}>{item.icon}</span> : null}
            <span>{item.label}</span>
          </Menu.Item>
        </Fragment>)}
      </Menu.Content>
    </Menu.Portal>
  </Menu.Root>;
}

export default DropdownMenu;

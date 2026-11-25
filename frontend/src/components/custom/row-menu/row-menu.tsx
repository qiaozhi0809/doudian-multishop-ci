import { forwardRef } from 'react';
import { MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/arc/button/button';
import { DropdownMenu, type DropdownItem } from '@/components/arc/dropdown-menu/dropdown-menu';
import Tooltip from '@/components/arc/tooltip/tooltip';

export type RowMenuItem = DropdownItem;

export interface RowMenuProps {
  items: RowMenuItem[];
  /** 触发按钮的读屏名和悬停提示，默认「更多操作」。 */
  label?: string;
}

const Trigger = forwardRef<HTMLButtonElement, { label: string }>(function Trigger({ label, ...rest }, ref) {
  return (
    <Tooltip content={label}>
      <Button ref={ref} variant="secondary" size="sm" iconOnly aria-label={label} {...rest}>
        <MoreHorizontal aria-hidden="true" />
      </Button>
    </Tooltip>
  );
});

/** 行尾「⋯」菜单：32 高图标按钮 + 菜单（图标、红色危险项、禁用项）。一行只露一个主按钮，其余收进这里。 */
export function RowMenu({ items, label = '更多操作' }: RowMenuProps) {
  return <DropdownMenu items={items} trigger={<Trigger label={label} />} />;
}

export default RowMenu;

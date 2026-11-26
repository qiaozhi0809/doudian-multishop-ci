import type { ReactNode } from "react";
import { Bell as BellIcon } from "lucide-react";
import { Button } from "@/components/arc/button/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/arc/popover/popover";
import styles from "../notification-center.module.css";

interface BellProps {
  unread: number;
  /** 有未解决的强提醒：徽标为红色 */
  urgent: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 面板内容 */
  children: ReactNode;
}

/** 右上角铃铛：纯图标按钮 + 未读数徽标，点开为右上展开的通知面板。 */
export function Bell({ unread, urgent, open, onOpenChange, children }: BellProps) {
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <span className={styles.bellWrap}>
        <PopoverTrigger asChild>
          <Button variant="ghost" iconOnly aria-label="通知">
            <BellIcon size={20} strokeWidth={1.75} aria-hidden="true" />
          </Button>
        </PopoverTrigger>
        {unread > 0 && (
          <span className={styles.count} data-urgent={urgent} data-testid="notification-count" aria-hidden="true">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </span>
      <PopoverContent align="end" sideOffset={8} className={styles.panel} aria-label="通知">
        {children}
      </PopoverContent>
    </Popover>
  );
}

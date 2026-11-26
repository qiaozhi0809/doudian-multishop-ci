import type { ReactNode } from "react";
import { Bell } from "./components/bell";
import { Panel } from "./components/panel";
import { StrongBanner } from "./components/strong-banner";
import { NotificationCenterContext, useNotificationCenter, useNotificationCenterState } from "./hooks/use-notification-center";
import { bannerView } from "./logic/notification-view";

/** 通知中心的状态只建一次（需在 NoticeProvider 与路由里），铃铛与横条共用。 */
export function NotificationCenterProvider({ children }: { children: ReactNode }) {
  const value = useNotificationCenterState();
  return <NotificationCenterContext.Provider value={value}>{children}</NotificationCenterContext.Provider>;
}

/** 右上角铃铛与通知面板。 */
export function NotificationBell() {
  const c = useNotificationCenter();
  return (
    <Bell unread={c.unread} urgent={c.strongOpen.length > 0} open={c.open} onOpenChange={c.setOpen}>
      <Panel
        progress={c.progress}
        items={c.items}
        total={c.total}
        pageSize={c.pageSize}
        page={c.page}
        onPageChange={c.setPage}
        unread={c.unread}
        unreadOnly={c.unreadOnly}
        onUnreadOnlyChange={c.setUnreadOnly}
        muted={c.muted}
        onMutedChange={c.setMuted}
        loading={c.loading}
        error={c.error}
        onRetry={c.retry}
        onOpenItem={c.openItem}
        onMarkAllRead={() => void c.markAllRead()}
      />
    </Bell>
  );
}

/** 全站顶部的强提醒横条。 */
export function NotificationBanner() {
  const c = useNotificationCenter();
  return <StrongBanner view={bannerView(c.strongOpen)} onNavigate={c.go} onOpenPanel={() => c.setOpen(true)} />;
}

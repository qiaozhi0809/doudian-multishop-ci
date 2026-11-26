import { createContext, useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { NotificationItem } from "../logic/notification-view";
import { useAlertNotices } from "./use-alert-notices";
import { useMuted } from "./use-muted";
import { useNotifications } from "./use-notifications";
import { useProgress, useProgressSubscriptions } from "./use-progress";

/**
 * 通知中心的全部状态，只在外壳里建一次：列表与摘要、进行中任务（SSE 订阅只挂这一处）、
 * 右下角弹窗（见 useAlertNotices）、面板开关与跳转。
 */
export function useNotificationCenterState() {
  const center = useNotifications();
  useProgressSubscriptions();
  const progress = useProgress();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [muted, setMuted] = useMuted();

  useAlertNotices(center.strongOpen);

  const go = (link: string | null) => {
    setOpen(false);
    if (link) void navigate(link);
  };
  const openItem = (item: NotificationItem) => {
    if (item.read_at === null) void center.markRead(item.id);
    go(item.link);
  };

  return { ...center, progress, open, setOpen, muted, setMuted, go, openItem };
}

export type NotificationCenterState = ReturnType<typeof useNotificationCenterState>;

export const NotificationCenterContext = createContext<NotificationCenterState | null>(null);

/** 铃铛与横条读同一份状态；必须在 NotificationCenterProvider 里使用。 */
export function useNotificationCenter(): NotificationCenterState {
  const value = useContext(NotificationCenterContext);
  if (!value) throw new Error("useNotificationCenter 需要 NotificationCenterProvider");
  return value;
}

import { useCallback } from "react";
import { notifyStrong } from "../logic/alert-channel";
import type { NotificationItem } from "../logic/notification-view";
import { readMuted } from "./use-muted";

/** 强提醒到来时调用：读取本地静音开关与页面可见性，响提示音并按需发系统通知。 */
export function useAlertChannel(): (item: NotificationItem) => void {
  return useCallback((item: NotificationItem) => {
    void notifyStrong(item, { muted: readMuted(), documentHidden: document.hidden });
  }, []);
}

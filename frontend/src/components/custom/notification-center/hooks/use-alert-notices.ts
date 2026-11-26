import { useNotice } from "@/components/custom/notice/notice";
import { alertNotice } from "../logic/notification-view";
import { useAlertChannel } from "./use-alert-channel";
import { useNotificationAlerts } from "./use-notifications";

/**
 * 新提醒到来：强档响提示音并按需发系统通知；事件类再弹右下角弹窗（强档常驻、中档 5 秒、弱档不弹）。
 * 状态类强提醒不弹窗，由顶部横条常驻显示、恢复后自动消失。
 */
export function useAlertNotices(): void {
  const notify = useNotice();
  const alertStrong = useAlertChannel();

  useNotificationAlerts((item) => {
    if (item.level === "strong") alertStrong(item);
    const notice = alertNotice(item);
    if (notify && notice) {
      const { text, tone, ...options } = notice;
      notify(text, tone, options);
    }
  });
}

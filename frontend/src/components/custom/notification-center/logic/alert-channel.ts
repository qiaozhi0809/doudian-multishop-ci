import type { NotificationItem } from "./notification-view";

/** 提示音文件（public/sounds，自行生成的短音）。 */
export const ALERT_SOUND_URL = "/sounds/alert.wav";

export interface AlertChannelOptions {
  muted: boolean;
  documentHidden: boolean;
}

export interface AlertChannelResult {
  played: boolean;
  shown: boolean;
}

async function playSound(): Promise<boolean> {
  try {
    await new Audio(ALERT_SOUND_URL).play();
    return true;
  } catch {
    // 浏览器拒绝自动播放（用户尚未交互）等情况：吞掉
    return false;
  }
}

async function showSystemNotification(item: NotificationItem): Promise<boolean> {
  try {
    if (typeof Notification === "undefined") return false;
    let permission = Notification.permission;
    // 第一次真正需要系统通知时才请求权限，不在页面加载时请求
    if (permission === "default") permission = await Notification.requestPermission();
    if (permission !== "granted") return false;
    new Notification(item.title, { body: item.body ?? undefined, tag: String(item.id) });
    return true;
  } catch {
    return false;
  }
}

/** 强提醒的提示音与系统通知：静音不响；系统通知只在页面不在前台时发。任何失败都吞掉。 */
export async function notifyStrong(
  item: NotificationItem,
  { muted, documentHidden }: AlertChannelOptions,
): Promise<AlertChannelResult> {
  const [played, shown] = await Promise.all([
    muted ? Promise.resolve(false) : playSound(),
    documentHidden ? showSystemNotification(item) : Promise.resolve(false),
  ]);
  return { played, shown };
}

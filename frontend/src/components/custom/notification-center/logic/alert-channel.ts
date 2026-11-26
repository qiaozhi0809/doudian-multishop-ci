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

/**
 * 申请系统通知权限。只能在用户操作（点铃铛、打开提示音开关）里调用：
 * 页面在后台、没有用户手势时浏览器不会弹窗。已决定或不支持时不再请求。
 */
export async function ensureNotificationPermission(): Promise<NotificationPermission | "unsupported"> {
  if (typeof Notification === "undefined") return "unsupported";
  try {
    if (Notification.permission !== "default") return Notification.permission;
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

/** 只读取权限，从不请求。 */
function showSystemNotification(item: NotificationItem): boolean {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return false;
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
    muted ? false : playSound(),
    documentHidden && showSystemNotification(item),
  ]);
  return { played, shown };
}

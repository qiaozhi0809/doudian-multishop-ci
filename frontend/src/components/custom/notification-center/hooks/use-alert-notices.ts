import { useEffect, useRef } from "react";
import { useNotice, useNoticeDismiss } from "@/components/custom/notice/notice";
import { useEventSubscription } from "@/lib/use-events";
import {
  alertNotice,
  isStillOpen,
  noticeKey,
  type NotificationEvent,
  type NotificationItem,
  type StrongOpenShop,
} from "../logic/notification-view";
import { useNotificationAlerts } from "./use-notifications";

interface Shown {
  shopId: number;
  kind: NotificationItem["kind"];
  /** 已在摘要里出现过：之后从摘要消失才算恢复（刚弹出时摘要可能还没刷新） */
  seen: boolean;
}

/**
 * 右下角弹窗：强档常驻、中档 5 秒、弱档不弹。
 * 状态类强提醒在问题恢复后自动收起：收到该条的 `resolved` 事件，或摘要里不再有该店该问题。
 */
export function useAlertNotices(strongOpen: StrongOpenShop[]): void {
  const notify = useNotice();
  const dismiss = useNoticeDismiss();
  const shown = useRef(new Map<string, Shown>());

  const close = (key: string) => {
    shown.current.delete(key);
    dismiss?.(key);
  };

  useNotificationAlerts((item) => {
    const notice = alertNotice(item);
    if (!notify || !notice) return;
    notify(notice.text, notice.tone, { key: notice.key, persistent: notice.persistent, holdMs: notice.holdMs });
    if (notice.persistent && item.state_key !== null && item.shop_id !== null) {
      shown.current.set(notice.key, { shopId: item.shop_id, kind: item.kind, seen: false });
    }
  });

  useEventSubscription<NotificationEvent>("notification", (event) => {
    if (event.action === "resolved" && event.item) close(noticeKey(event.item.id));
  });

  useEffect(() => {
    for (const [key, entry] of shown.current) {
      if (isStillOpen(strongOpen, entry.shopId, entry.kind)) shown.current.set(key, { ...entry, seen: true });
      else if (entry.seen) {
        shown.current.delete(key);
        dismiss?.(key);
      }
    }
  }, [strongOpen, dismiss]);
}

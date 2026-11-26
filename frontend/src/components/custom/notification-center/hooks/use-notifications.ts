import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ActionResult } from "@/lib/action-result";
import { api, errorText } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import {
  shouldAlert,
  type NotificationEvent,
  type NotificationItem,
  type NotificationPage,
  type NotificationSummary,
} from "../logic/notification-view";

/** 本会话已弹过提醒的通知 id；存 sessionStorage，刷新页面不重复弹。 */
export const ALERTED_KEY = "notify.alerted";
const ALERTED_LIMIT = 200;

function readAlerted(): number[] {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(ALERTED_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((x): x is number => typeof x === "number") : [];
  } catch {
    return [];
  }
}

function rememberAlerted(id: number): void {
  try {
    sessionStorage.setItem(ALERTED_KEY, JSON.stringify([...readAlerted(), id].slice(-ALERTED_LIMIT)));
  } catch {
    // 存储不可用时只是可能重复提醒，不影响功能
  }
}

/** 通知列表与摘要：`notification` 事件与 SSE 重连（`open`）都让通知查询失效，断线期间的通知不会漏。 */
export function useNotifications() {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnlyState] = useState(false);

  const list = useQuery({
    queryKey: queryKeys.notifications(unreadOnly, page),
    queryFn: () => api.get<NotificationPage>("/api/notifications", { unread: unreadOnly || undefined, page }),
  });
  const summary = useQuery({
    queryKey: queryKeys.notificationSummary(),
    queryFn: () => api.get<NotificationSummary>("/api/notifications/summary"),
  });

  const refresh = () => client.invalidateQueries({ queryKey: queryKeys.notificationsRoot() });
  useEventSubscription("notification", () => void refresh());
  useEventSubscription("open", () => void refresh());

  const write = async (path: string): Promise<ActionResult> => {
    try {
      await api.post(path);
      await refresh();
      return { ok: true };
    } catch (e) {
      return { ok: false, error: errorText(e) };
    }
  };

  const setUnreadOnly = (value: boolean) => {
    setUnreadOnlyState(value);
    setPage(1);
  };

  return {
    items: list.data?.items ?? [],
    total: list.data?.total ?? 0,
    pageSize: list.data?.page_size ?? 0,
    unread: summary.data?.unread ?? 0,
    strongOpen: summary.data?.strong_open ?? [],
    page,
    setPage,
    unreadOnly,
    setUnreadOnly,
    markRead: (id: number) => write(`/api/notifications/${id}/read`),
    markAllRead: () => write("/api/notifications/read-all"),
    loading: list.isPending || summary.isPending,
  };
}

/** 只对 `alert === true` 且本会话未提醒过的通知回调一次。 */
export function useNotificationAlerts(onAlert: (item: NotificationItem) => void): void {
  useEventSubscription<NotificationEvent>("notification", (event) => {
    if (!shouldAlert(event, readAlerted()) || event.item === null) return;
    rememberAlerted(event.item.id);
    onAlert(event.item);
  });
}

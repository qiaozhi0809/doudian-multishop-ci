import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";

const LOGIN_WAIT_TIMEOUT_MS = 10 * 60 * 1000;
const FALLBACK_ERROR = "请求失败，请确认本地服务正常后重试";

const errorText = (e: unknown): string => (e instanceof ApiError ? e.message : FALLBACK_ERROR);

/**
 * 顶栏会话健康里的一键重登：发起扫码 → 等待态 → SSE 结束（成功失效店铺查询 / 失败留在行内）。
 * 不改店铺页的登录流程，只作为外壳里的快捷入口。
 */
export function useQuickLogin() {
  const client = useQueryClient();
  const [pendingIds, setPendingIds] = useState<number[]>([]);
  const [waitingIds, setWaitingIds] = useState<number[]>([]);
  const [errors, setErrors] = useState<Record<number, string>>({});
  const waitingRef = useRef<number[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  useEffect(
    () => () => {
      timers.current.forEach((timer) => clearTimeout(timer));
      timers.current.clear();
    },
    [],
  );

  const setWaiting = useCallback((ids: number[]) => {
    waitingRef.current = ids;
    setWaitingIds(ids);
  }, []);

  const finish = useCallback(
    (shopId: number) => {
      const timer = timers.current.get(shopId);
      if (timer) clearTimeout(timer);
      timers.current.delete(shopId);
      setWaiting(waitingRef.current.filter((id) => id !== shopId));
    },
    [setWaiting],
  );

  const clearError = useCallback((shopId: number) => {
    setErrors((prev) => {
      if (!(shopId in prev)) return prev;
      const next = { ...prev };
      delete next[shopId];
      return next;
    });
  }, []);

  useEventSubscription<{ shop_id: number; status?: string }>("shop_status_changed", (data) => {
    if (data.status !== "active" || !waitingRef.current.includes(data.shop_id)) return;
    finish(data.shop_id);
    clearError(data.shop_id);
    void client.invalidateQueries({ queryKey: queryKeys.shops() });
  });

  useEventSubscription<{ shop_id: number; reason: string }>("shop_login_failed", (data) => {
    if (!waitingRef.current.includes(data.shop_id)) return;
    finish(data.shop_id);
    setErrors((prev) => ({ ...prev, [data.shop_id]: data.reason }));
  });

  const login = useCallback(
    async (shopId: number) => {
      setPendingIds((prev) => [...prev, shopId]);
      clearError(shopId);
      try {
        await api.post(`/api/shops/${shopId}/login`);
      } catch (e) {
        setErrors((prev) => ({ ...prev, [shopId]: errorText(e) }));
        return;
      } finally {
        setPendingIds((prev) => prev.filter((id) => id !== shopId));
      }
      setWaiting([...waitingRef.current.filter((id) => id !== shopId), shopId]);
      timers.current.set(
        shopId,
        setTimeout(() => {
          if (!waitingRef.current.includes(shopId)) return;
          finish(shopId);
          setErrors((prev) => ({ ...prev, [shopId]: "等待扫码超时，请重新发起扫码登录" }));
        }, LOGIN_WAIT_TIMEOUT_MS),
      );
    },
    [clearError, finish, setWaiting],
  );

  return { pendingIds, waitingIds, errors, login };
}

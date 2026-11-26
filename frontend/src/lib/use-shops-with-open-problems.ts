import { useMemo } from "react";
import { queryOptions, useQuery } from "@tanstack/react-query";
import { api } from "./api-client";
import type { components } from "./api-types";
import { shopsWithOpenProblems } from "./open-problem-shops";
import { queryKeys } from "./query-keys";

type NotificationSummary = components["schemas"]["NotificationSummary"];

/** 通知摘要（未读数 + 未解决的强提醒）；通知中心与各页共用同一份缓存。 */
export const notificationSummaryQuery = () =>
  queryOptions({
    queryKey: queryKeys.notificationSummary(),
    queryFn: () => api.get<NotificationSummary>("/api/notifications/summary"),
  });

const NONE: ReadonlySet<number> = new Set();

/**
 * 横条里有登录 / 出口 / 风控问题的店。读通知中心已有的摘要缓存：挂载时不重取，
 * 通知事件让摘要失效重取时跟着更新。
 */
export function useShopsWithOpenProblems(): ReadonlySet<number> {
  const { data } = useQuery({ ...notificationSummaryQuery(), staleTime: Infinity });
  const strongOpen = data?.strong_open;
  return useMemo(() => (strongOpen ? shopsWithOpenProblems(strongOpen) : NONE), [strongOpen]);
}

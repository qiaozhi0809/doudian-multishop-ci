import { useCallback, useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { useNoticeQueue } from "@/components/custom/notice/use-notice-queue";
import { api, errorText } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import { useListSort } from "@/lib/use-list-sort";
import { useQuickFilter } from "@/lib/use-quick-filter";
import {
  IM_QUICK,
  IM_SORT_KEYS,
  PAGE_SIZE,
  clampPage,
  inShopScope,
  selectionParam,
  stoppedShops,
  type ConversationPage,
  type Counts,
  type Selection,
  type ShopStatus,
} from "../logic/message-page";

export const IM_REFETCH_MS = 30_000;

/** 每秒走一次的时钟：等待时间走秒、超时标红。 */
function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

/** 飞鸽事件到达时消息页的数据全部重取。 */
function useImEvents() {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: queryKeys.imRoot() });
  useEventSubscription("im_unread_changed", refresh);
  useEventSubscription("im_wait_changed", refresh);
  useEventSubscription("im_stopped", refresh);
}

/** 未在接收的店「重新连接」。 */
function useRestart() {
  const client = useQueryClient();
  const { notices, notify, dismissNotice } = useNoticeQueue();
  const [pending, setPending] = useState<ReadonlySet<number>>(new Set());
  const mutation = useMutation({
    mutationFn: (shopId: number) => api.post<ShopStatus>(`/api/im/shops/${shopId}/restart`),
    onMutate: (shopId) => setPending((prev) => new Set(prev).add(shopId)),
    onError: (error, shopId) => notify(`im-restart-${shopId}`, "danger", errorText(error)),
    onSettled: (_data, _error, shopId) => {
      setPending((prev) => new Set([...prev].filter((id) => id !== shopId)));
      return client.invalidateQueries({ queryKey: queryKeys.imRoot() });
    },
  });
  return { restart: (shopId: number) => mutation.mutate(shopId), pending, notices, dismissNotice };
}

/** 消息页左侧与顶部的数据：筛选、排序、页码、选中项都在 URL 里。 */
export function useMessagePage() {
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();
  const quick = useQuickFilter(IM_QUICK);
  const sorting = useListSort(IM_SORT_KEYS);
  const unreadOnly = params.get("unread") === "1";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const selected = selectionParam.read(params);
  const selection = selected && inShopScope(selected.shopId, shopIds) ? selected : null;

  const filters = { unread: unreadOnly || undefined, page, ...sorting.query, ...quick.query };
  const list = useQuery({
    queryKey: queryKeys.imConversations(shopIds, filters),
    queryFn: () =>
      api.get<ConversationPage>("/api/im/conversations", { shop_ids: shopIds, ...filters, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
    refetchInterval: IM_REFETCH_MS,
  });
  const counts = useQuery({
    queryKey: queryKeys.imCounts(shopIds),
    queryFn: () => api.get<Counts>("/api/im/conversations/counts", { shop_ids: shopIds }),
    placeholderData: keepPreviousData,
    refetchInterval: IM_REFETCH_MS,
  });
  const status = useQuery({
    queryKey: queryKeys.imStatus(),
    queryFn: () => api.get<ShopStatus[]>("/api/im/status"),
    refetchInterval: IM_REFETCH_MS,
  });
  useImEvents();

  const setPage = useCallback(
    (value: number, replace = false) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value > 1) next.set("page", String(value));
          else next.delete("page");
          return next;
        },
        { replace },
      ),
    [setParams],
  );
  const setUnreadOnly = (value: boolean) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set("unread", "1");
      else next.delete("unread");
      next.delete("page");
      return next;
    });
  const select = (value: Selection) => setParams((prev) => selectionParam.write(prev, value));

  const total = list.isPlaceholderData ? undefined : list.data?.total;
  useEffect(() => {
    if (total === undefined) return;
    const last = clampPage(page, total, PAGE_SIZE);
    if (last !== page) setPage(last, true);
  }, [total, page, setPage]);

  const now = useNow();
  const restart = useRestart();
  return {
    now,
    quick,
    unreadOnly,
    setUnreadOnly,
    page,
    setPage,
    selection,
    select,
    list,
    counts,
    status,
    stopped: stoppedShops(status.data ?? [], shopIds),
    restart,
  };
}

export type MessagePageState = ReturnType<typeof useMessagePage>;

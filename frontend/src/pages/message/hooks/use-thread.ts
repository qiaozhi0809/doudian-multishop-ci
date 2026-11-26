import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNoticeQueue } from "@/components/custom/notice/use-notice-queue";
import { api, errorText } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { useLastPresent } from "@/lib/use-last-present";
import {
  selectionKey,
  type Conversation,
  type FocusResult,
  type Selection,
  type Thread,
} from "../logic/message-page";
import { IM_REFETCH_MS } from "./use-message-page";

const NOTICE_KEY = "im-open-flybird";
const NOT_FOUND_TEXT = "飞鸽里没找到该会话";

const threadPath = ({ shopId, conversationId }: Selection) =>
  `/api/im/conversations/${shopId}/${encodeURIComponent(conversationId)}`;

/**
 * 右栏：选中会话的消息记录与「在飞鸽中回复」。
 * row 是该会话在当前列表里的行；筛选或翻页后不在列表里时，抬头沿用上一次看到的行。
 */
export function useThread(selection: Selection | null, row: Conversation | undefined) {
  const key = selection ? selectionKey(selection.shopId, selection.conversationId) : null;
  const last = useLastPresent(row);
  const known = last && selectionKey(last.shop_id, last.conversation_id) === key ? last : undefined;

  const messages = useQuery({
    queryKey: queryKeys.imThread(selection?.shopId ?? 0, selection?.conversationId ?? ""),
    queryFn: () => api.get<Thread>(`${threadPath(selection!)}/messages`),
    enabled: selection !== null,
    refetchInterval: IM_REFETCH_MS,
  });

  const { notices, notify, dismissNotice } = useNoticeQueue();
  const [opening, setOpening] = useState<ReadonlySet<string>>(new Set());
  const open = useMutation({
    mutationFn: (target: Selection) => api.post<FocusResult>(`${threadPath(target)}/open-in-flybird`),
    onMutate: (target) => setOpening((prev) => new Set(prev).add(selectionKey(target.shopId, target.conversationId))),
    onSuccess: ({ result }) => {
      if (result === "not_found") notify(NOTICE_KEY, "warning", NOT_FOUND_TEXT);
    },
    onError: (error) => notify(NOTICE_KEY, "danger", errorText(error)),
    onSettled: (_data, _error, target) => {
      const done = selectionKey(target.shopId, target.conversationId);
      setOpening((prev) => new Set([...prev].filter((item) => item !== done)));
    },
  });

  return {
    selection,
    messages,
    /** 读取消息失败的原因。 */
    loadError: messages.error ? errorText(messages.error) : null,
    /** 当前列表里的行：等待时间只信它。 */
    row,
    /** 抬头与预览用：当前行，或上一次看到的同一会话。 */
    known,
    opening: key !== null && opening.has(key),
    openInFlybird: () => {
      if (selection) open.mutate(selection);
    },
    notices,
    dismissNotice,
  };
}

export type ThreadState = ReturnType<typeof useThread>;

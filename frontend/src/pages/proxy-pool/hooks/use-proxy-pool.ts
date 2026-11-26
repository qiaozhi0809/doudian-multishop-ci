import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ActionResult } from "@/lib/action-result";
import { api, errorText } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { usePoolItems, type PoolItem } from "@/lib/use-pool-items";

type Schemas = components["schemas"];
export type { ActionResult, PoolItem };
export type PoolImportOut = Schemas["PoolImportOut"];
export type PoolCheckOut = Schemas["PoolCheckOut"];
export type PoolPatch = Schemas["PoolPatch"];

export type Failure = { error: string };

/** 代理池：列表、导入、编辑、删除、检查。写操作成功后同时刷新池与店铺（占用关系在两边都可见）。 */
export function useProxyPool() {
  const client = useQueryClient();
  const [pendingIds, setPendingIds] = useState<number[]>([]);
  const list = usePoolItems();
  const refresh = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.proxyPool() }),
      client.invalidateQueries({ queryKey: queryKeys.shops() }),
    ]);

  const importMutation = useMutation({
    mutationFn: (text: string) => api.post<PoolImportOut>("/api/proxy-pool/import", { text }),
    onSuccess: refresh,
  });

  const track = async <T,>(id: number, fn: () => Promise<T>): Promise<T> => {
    setPendingIds((p) => [...p, id]);
    try {
      return await fn();
    } finally {
      setPendingIds((p) => p.filter((x) => x !== id));
    }
  };

  const importText = async (text: string): Promise<PoolImportOut | Failure> => {
    try {
      return await importMutation.mutateAsync(text);
    } catch (e) {
      return { error: errorText(e) };
    }
  };

  const update = (id: number, patch: PoolPatch): Promise<ActionResult> =>
    track(id, async () => {
      try {
        await api.patch<PoolItem>(`/api/proxy-pool/${id}`, patch);
        await refresh();
        return { ok: true as const };
      } catch (e) {
        return { ok: false as const, error: errorText(e) };
      }
    });

  const remove = (id: number): Promise<ActionResult> =>
    track(id, async () => {
      try {
        await api.delete(`/api/proxy-pool/${id}`);
        await refresh();
        return { ok: true as const };
      } catch (e) {
        return { ok: false as const, error: errorText(e) };
      }
    });

  const check = (id: number): Promise<PoolCheckOut | Failure> =>
    track(id, async () => {
      try {
        const result = await api.post<PoolCheckOut>(`/api/proxy-pool/${id}/check`);
        await client.invalidateQueries({ queryKey: queryKeys.proxyPool() });
        return result;
      } catch (e) {
        return { error: errorText(e) };
      }
    });

  return {
    items: list.data ?? [],
    loading: list.isLoading,
    failed: list.isError,
    retry: () => void list.refetch(),
    importing: importMutation.isPending,
    importText,
    update,
    remove,
    check,
    pendingIds,
  };
}

export type ProxyPoolState = ReturnType<typeof useProxyPool>;

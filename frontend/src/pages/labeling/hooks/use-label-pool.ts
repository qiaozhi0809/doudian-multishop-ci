import { useCallback, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import {
  PAGE_SIZE,
  allSelected,
  isStage,
  pruneSelection,
  toggleAll,
  type LabelOrder,
  type Stage,
} from "../logic/label-columns";

/** 打单发货订单池：阶段与页码在 URL 里；勾选集合在刷新之间保留（失效行自动移除）。 */
export function useLabelPool() {
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();

  const stageParam = params.get("stage");
  const stage: Stage = isStage(stageParam) ? stageParam : "pending";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;

  const setStage = useCallback(
    (next: Stage) =>
      setParams((prev) => {
        const p = new URLSearchParams(prev);
        if (next === "pending") p.delete("stage");
        else p.set("stage", next);
        p.delete("page");
        return p;
      }),
    [setParams],
  );

  const setPage = useCallback(
    (next: number) =>
      setParams((prev) => {
        const p = new URLSearchParams(prev);
        if (next > 1) p.set("page", String(next));
        else p.delete("page");
        return p;
      }),
    [setParams],
  );

  const query = useQuery({
    queryKey: queryKeys.labelPool(shopIds, { stage, page }),
    queryFn: () =>
      api.get<components["schemas"]["LabelPoolPage"]>("/api/labels/pool", {
        shop_ids: shopIds,
        stage,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const rows = useMemo(() => query.data?.items ?? [], [query.data]);

  // 勾选状态保存原始 id；每次渲染只暴露仍然存在且可选中的部分（SSE 刷新不丢选择）。
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const effective = useMemo(() => pruneSelection(selected, rows), [selected, rows]);

  const toggle = useCallback(
    (id: number) => {
      setSelected((prev) => {
        const next = new Set(pruneSelection(prev, rows));
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    },
    [rows],
  );

  const toggleAllRows = useCallback(() => {
    setSelected((prev) => toggleAll(pruneSelection(prev, rows), rows));
  }, [rows]);

  return {
    query,
    rows,
    stage,
    page,
    setStage,
    setPage,
    selected: effective,
    toggle,
    toggleAll: toggleAllRows,
    allChecked: allSelected(effective, rows),
    clearSelection: () => setSelected(new Set()),
  };
}

export type LabelRow = LabelOrder;

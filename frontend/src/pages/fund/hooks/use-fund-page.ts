import { useCallback, useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useShops } from "@/lib/use-shops";
import {
  UNSETTLED_PAGE_SIZE,
  isFundTab,
  parseBillDays,
  type FundTab,
} from "../logic/fund-page";
import { useFundSync } from "./use-fund-sync";

type Summary = components["schemas"]["FundSummary"];
type UnsettledPage = components["schemas"]["UnsettledPage"];
type MarginResponse = components["schemas"]["MarginResponse"];
type BillsResponse = components["schemas"]["BillsResponse"];

/** 资金页数据：标签页 / 页码 / 账单天数在 URL 里。汇总来自本地快照，账单每次从上游取。 */
export function useFundPage() {
  const shops = useShops();
  const { shopIds } = useShopFilter();
  const [params, setParams] = useSearchParams();

  const rawTab = params.get("tab");
  const tab: FundTab = isFundTab(rawTab) ? rawTab : "unsettled";
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1;
  const days = parseBillDays(params.get("days"));

  const update = useCallback(
    (patch: { tab?: FundTab; page?: number; days?: number }) =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (patch.tab !== undefined) {
          if (patch.tab === "unsettled") next.delete("tab");
          else next.set("tab", patch.tab);
          next.delete("page");
        }
        if (patch.days !== undefined) {
          if (patch.days === 30) next.delete("days");
          else next.set("days", String(patch.days));
          next.delete("page");
        }
        if (patch.page !== undefined) {
          if (patch.page > 1) next.set("page", String(patch.page));
          else next.delete("page");
        }
        return next;
      }),
    [setParams],
  );

  const summary = useQuery({
    queryKey: queryKeys.fundSummary(shopIds),
    queryFn: () => api.get<Summary>("/api/fund/summary", { shop_ids: shopIds }),
  });

  const unsettled = useQuery({
    queryKey: queryKeys.fundUnsettled(shopIds, page),
    queryFn: () =>
      api.get<UnsettledPage>("/api/fund/unsettled", {
        shop_ids: shopIds, page, page_size: UNSETTLED_PAGE_SIZE,
      }),
    enabled: tab === "unsettled",
    placeholderData: keepPreviousData,
  });

  const margin = useQuery({
    queryKey: queryKeys.fundMargin(shopIds),
    queryFn: () => api.get<MarginResponse>("/api/fund/margin", { shop_ids: shopIds }),
    enabled: tab === "margin",
  });

  const bills = useQuery({
    queryKey: queryKeys.fundBills(shopIds, days),
    queryFn: () => api.get<BillsResponse>("/api/fund/bills", { shop_ids: shopIds, days }),
    enabled: tab === "bills",
    placeholderData: keepPreviousData,
  });

  const sync = useFundSync();
  const names = useMemo(
    () => new Map((shops.data ?? []).map((s) => [s.id, s.name])),
    [shops.data],
  );

  return {
    shopsState: shops.isLoading
      ? ("loading" as const)
      : shops.isError
        ? ("error" as const)
        : (shops.data ?? []).length === 0
          ? ("empty" as const)
          : ("ready" as const),
    retryShops: () => void shops.refetch(),
    shopName: (id: number) => names.get(id) ?? `店铺 ${id}`,
    tab,
    setTab: (value: FundTab) => update({ tab: value }),
    page,
    setPage: (value: number) => update({ page: value }),
    days,
    setDays: (value: number) => update({ days: value }),
    summary,
    unsettled,
    margin,
    bills,
    sync,
  };
}

export type FundPageState = ReturnType<typeof useFundPage>;

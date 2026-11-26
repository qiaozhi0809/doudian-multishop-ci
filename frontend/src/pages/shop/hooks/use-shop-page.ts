import { useSearchParams } from "react-router-dom";
import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { useShops, type ShopRow } from "@/lib/use-shops";
import { useBackup } from "./use-backup";
import { useShopActions } from "./use-shop-actions";
import { useShopBase } from "./use-shop-base";
import { useShopDialogs } from "./use-shop-dialogs";

/** 通知跳转高亮的店铺参数（全局店铺筛选是 `shops`）。 */
export const HIGHLIGHT_PARAM = "shop";

/** 店铺页的全部数据与动作：列表（按全局店铺筛选）、`?shop=<id>` 高亮、操作、对话框状态、数据备份。 */
export function useShopPage() {
  const query = useShops();
  const { shopIds } = useShopFilter();
  const [params] = useSearchParams();
  const highlight = Number(params.get(HIGHLIGHT_PARAM));
  const all = query.data ?? [];
  const shops = shopIds.length ? all.filter((s) => shopIds.includes(s.id)) : all;
  const actions = useShopActions(all);
  const dialogs = useShopDialogs();
  const base = useShopBase(dialogs.baseShopId);
  const backup = useBackup();
  const byId = (id: number | null): ShopRow | null => all.find((s) => s.id === id) ?? null;

  return {
    status: query.isLoading ? ("loading" as const) : query.isError ? ("error" as const) : all.length === 0 ? ("empty" as const) : ("ready" as const),
    retry: () => void query.refetch(),
    shops,
    highlightId: Number.isInteger(highlight) && highlight > 0 ? highlight : null,
    allShops: all,
    actions,
    dialogs,
    backup,
    base: { query: base, shop: byId(dialogs.baseShopId) },
    egressShop: byId(dialogs.egressShopId),
    resumeShop: byId(dialogs.resumeShopId),
    editShop: byId(dialogs.editShopId),
    disableShop: byId(dialogs.disableShopId),
  };
}

export type ShopPage = ReturnType<typeof useShopPage>;

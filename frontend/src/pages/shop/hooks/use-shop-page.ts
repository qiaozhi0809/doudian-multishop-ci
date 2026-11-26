import { useShopFilter } from "@/components/custom/app-shell/hooks/use-shop-filter";
import { useShops, type ShopRow } from "@/lib/use-shops";
import { useBackup } from "./use-backup";
import { useShopActions } from "./use-shop-actions";
import { useShopBase } from "./use-shop-base";
import { useShopDialogs } from "./use-shop-dialogs";

/** 店铺页的全部数据与动作：列表（按全局店铺筛选）、操作、对话框状态、数据备份。 */
export function useShopPage() {
  const query = useShops();
  const { shopIds } = useShopFilter();
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

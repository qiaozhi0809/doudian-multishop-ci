import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { SHOP_FILTER_PARAM, parseShopFilter, serializeShopFilter } from "../logic/shop-filter";

/** 全局店铺筛选（URL 参数 `shops`）。各页面从这里取当前筛选；切换筛选回到第 1 页。 */
export function useShopFilter() {
  const [params, setParams] = useSearchParams();
  const raw = params.get(SHOP_FILTER_PARAM);
  const shopIds = useMemo(() => parseShopFilter(`?${SHOP_FILTER_PARAM}=${raw ?? ""}`), [raw]);

  const setShopIds = useCallback(
    (ids: number[]) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          const value = serializeShopFilter(ids);
          if (value) next.set(SHOP_FILTER_PARAM, value);
          else next.delete(SHOP_FILTER_PARAM);
          next.delete("page");
          return next;
        },
        { replace: false },
      );
    },
    [setParams],
  );

  return { shopIds, setShopIds };
}

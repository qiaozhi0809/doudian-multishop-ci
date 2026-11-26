import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { readSort, sortQuery, writeSort, type ListSort } from "./list-sort";

/** 分页列表的服务端排序：排序放在 URL（刷新、分享后保持），改排序回到第 1 页。allowed 与后端白名单一致。 */
export function useListSort(allowed: readonly string[]) {
  const [params, setParams] = useSearchParams();
  const sort = readSort(params, allowed);
  const setSort = useCallback((next: ListSort | null) => setParams((prev) => writeSort(prev, next)), [setParams]);
  return { sort, setSort, query: sortQuery(sort) };
}

const sameSort = (a: ListSort | null, b: ListSort | null) =>
  a === b || (a !== null && b !== null && a.key === b.key && a.direction === b.direction);

/**
 * 表头显示的排序：新排序的数据回来之前（keepPreviousData 的占位期）仍显示上一次的排序，
 * 免得箭头和底色先变、行还是旧顺序。settled = 当前数据就是按 sort 取回的。
 */
export function useSettledSort(sort: ListSort | null, settled: boolean): ListSort | null {
  const [shown, setShown] = useState(sort);
  if (settled && !sameSort(shown, sort)) {
    setShown(sort);
    return sort;
  }
  return settled ? sort : shown;
}

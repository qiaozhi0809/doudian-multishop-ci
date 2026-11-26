import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

export const QUICK_PARAM = "quick";

/** 从 URL 读快捷筛选；不在白名单里的值视为没有筛选（避免手改的 URL 换来 422）。 */
export function readQuick<K extends string>(params: URLSearchParams, allowed: readonly K[]): K | null {
  const value = params.get(QUICK_PARAM);
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as K) : null;
}

/** 切换快捷筛选：点当前选中的那张卡 = 清除；换筛选回到第 1 页。 */
export function writeQuick(prev: URLSearchParams, current: string | null, next: string | null): URLSearchParams {
  const params = new URLSearchParams(prev);
  if (next === null || next === current) params.delete(QUICK_PARAM);
  else params.set(QUICK_PARAM, next);
  params.delete("page");
  return params;
}

/**
 * 计数卡快捷筛选（全站一致）：筛选放在 URL 的 `quick=<键>`，和排序、页码一样刷新后保持，
 * 原样发给后端白名单参数，在 SQL 里筛完再分页。allowed 与后端 Literal 一致。
 */
export function useQuickFilter<K extends string>(allowed: readonly K[]) {
  const [params, setParams] = useSearchParams();
  const quick = readQuick(params, allowed);
  const toggle = useCallback(
    (key: K | null) => setParams((prev) => writeQuick(prev, readQuick(prev, allowed), key)),
    [setParams, allowed],
  );
  /** 给 MetricCard 的 selected / onSelect。 */
  const cardProps = (key: K) => ({ selected: quick === key, onSelect: () => toggle(key) });
  return { quick, toggle, cardProps, query: quick ? { quick } : {} };
}

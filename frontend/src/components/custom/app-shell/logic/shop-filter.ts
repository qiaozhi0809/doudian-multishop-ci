/** 店铺筛选存在 URL 参数 `shops=1,2`（空 = 全部）。 */
export const SHOP_FILTER_PARAM = "shops";

/** 从查询串读取店铺 id：只保留正整数，去重，保持出现顺序。 */
export function parseShopFilter(search: string): number[] {
  const raw = new URLSearchParams(search).get(SHOP_FILTER_PARAM) ?? "";
  const ids: number[] = [];
  for (const part of raw.split(",")) {
    if (!/^\d+$/.test(part)) continue;
    const id = Number(part);
    if (id > 0 && !ids.includes(id)) ids.push(id);
  }
  return ids;
}

/** 参数值：升序、去重、逗号连接；空数组为空串（调用方据此删除参数）。 */
export function serializeShopFilter(ids: number[]): string {
  return [...new Set(ids)].sort((a, b) => a - b).join(",");
}

/** 给路径带上当前店铺筛选（页面间切换时保持筛选）。 */
export function withShopFilter(path: string, ids: number[]): string {
  const value = serializeShopFilter(ids);
  return value ? `${path}?${SHOP_FILTER_PARAM}=${value}` : path;
}

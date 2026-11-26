/** 空值统一显示「暂无」（ui-guidelines 6 节：不用 `-` 或 `—`）。 */
export const EMPTY_TEXT = "暂无";

/** 有值原样返回，空字符串 / null / undefined 显示「暂无」。 */
export const orEmpty = (value: string | null | undefined): string => value || EMPTY_TEXT;

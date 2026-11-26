import { useState } from "react";

/** 最近一次不为空的值：对话框关闭动画期间对象已被置空，标题仍显示刚才那一项，不闪成空白。 */
export function useLastPresent<T>(value: T | null | undefined): T | null {
  const [last, setLast] = useState<T | null>(value ?? null);
  if (value != null && value !== last) {
    setLast(value);
    return value;
  }
  return value ?? last;
}

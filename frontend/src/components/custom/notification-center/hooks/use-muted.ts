import { useState } from "react";

/** 提示音开关存在本地（强提醒的提示音由 Task 8 的提醒通道读取）。 */
export const MUTED_KEY = "notify.muted";

export function readMuted(): boolean {
  try {
    return localStorage.getItem(MUTED_KEY) === "1";
  } catch {
    return false;
  }
}

/** 提示音开关：`muted` 为 true 时不响。 */
export function useMuted(): [boolean, (muted: boolean) => void] {
  const [muted, setState] = useState(readMuted);
  const setMuted = (value: boolean) => {
    setState(value);
    try {
      localStorage.setItem(MUTED_KEY, value ? "1" : "0");
    } catch {
      // 存储不可用时只在本页生效
    }
  };
  return [muted, setMuted];
}

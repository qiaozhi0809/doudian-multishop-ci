import { useCallback, useState } from "react";

const KEY = "doudian.sideNavCollapsed";

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

/** 侧边栏收起状态，记在浏览器里；存储不可用时仍可切换。 */
export function useSideNavCollapsed() {
  const [collapsed, setCollapsed] = useState(read);
  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(KEY, next ? "1" : "0");
      } catch {
        // 存储不可用时只保留内存状态
      }
      return next;
    });
  }, []);
  return { collapsed, toggle };
}

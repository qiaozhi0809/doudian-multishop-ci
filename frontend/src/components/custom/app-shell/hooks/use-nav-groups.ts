import { useCallback, useState } from "react";
import {
  NAV_GROUP_STORAGE_KEY,
  parseCollapsedGroups,
  serializeCollapsedGroups,
  toggleCollapsedGroup,
} from "../logic/nav-groups";

function read(): string[] {
  try {
    return parseCollapsedGroups(localStorage.getItem(NAV_GROUP_STORAGE_KEY));
  } catch {
    return [];
  }
}

/** 侧边栏分组折叠状态：默认全部展开；存储不可用时只保留内存状态。 */
export function useNavGroups() {
  const [collapsed, setCollapsed] = useState<string[]>(read);

  const toggle = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = toggleCollapsedGroup(prev, id);
      try {
        localStorage.setItem(NAV_GROUP_STORAGE_KEY, serializeCollapsedGroups(next));
      } catch {
        // 存储不可用时只保留内存状态
      }
      return next;
    });
  }, []);

  return { collapsedGroups: new Set(collapsed), toggleGroup: toggle };
}

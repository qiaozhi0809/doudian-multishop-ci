import { NAV_SECTIONS } from "./nav-items";

/** 分组折叠状态记在浏览器里（frontend.md 1.1：可折叠、默认全部展开、状态记本地）。 */
export const NAV_GROUP_STORAGE_KEY = "doudian.navCollapsedGroups";

/** 已知的分组 id；存储里的其他值一律忽略。 */
export function knownGroupIds(): string[] {
  return NAV_SECTIONS.flatMap((section) => (section.kind === "group" ? [section.id] : []));
}

/** 解析已存的折叠分组：只保留合法 id，去重；坏数据当作全部展开。 */
export function parseCollapsedGroups(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const known = new Set(knownGroupIds());
    return [...new Set(parsed.filter((value): value is string => typeof value === "string" && known.has(value)))];
  } catch {
    return [];
  }
}

export function serializeCollapsedGroups(ids: string[]): string {
  const known = new Set(knownGroupIds());
  return JSON.stringify(ids.filter((id) => known.has(id)));
}

export function toggleCollapsedGroup(ids: string[], id: string): string[] {
  if (!knownGroupIds().includes(id)) return ids;
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
}

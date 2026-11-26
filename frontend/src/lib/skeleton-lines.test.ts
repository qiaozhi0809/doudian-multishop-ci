import { describe, expect, it } from "vitest";
import { SKELETON_LINES } from "./skeleton-lines";

describe("骨架行数约定", () => {
  it("每一档都在 Arc Skeleton 能画出的 1 到 6 行内", () => {
    for (const lines of Object.values(SKELETON_LINES)) {
      expect(lines).toBeGreaterThanOrEqual(1);
      expect(lines).toBeLessThanOrEqual(6);
    }
  });

  it("列表 6 行、卡片 4 行、计数行 2 行、单值 1 行", () => {
    expect(SKELETON_LINES).toEqual({ list: 6, card: 4, count: 2, value: 1 });
  });
});

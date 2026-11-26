import { describe, expect, it } from "vitest";
import { readQuick, writeQuick } from "./use-quick-filter";

const KEYS = ["alarm", "sold_out"] as const;

describe("快捷筛选", () => {
  it("只认白名单里的值", () => {
    expect(readQuick(new URLSearchParams("quick=alarm"), KEYS)).toBe("alarm");
    expect(readQuick(new URLSearchParams("quick=raw_json"), KEYS)).toBeNull();
    expect(readQuick(new URLSearchParams(""), KEYS)).toBeNull();
  });

  it("点卡片设为筛选并回到第 1 页，再点同一张清除；排序与关键字保留", () => {
    const prev = new URLSearchParams("q=甲&sort=price&order=desc&page=3");
    const set = writeQuick(prev, null, "alarm");
    expect(set.get("quick")).toBe("alarm");
    expect(set.get("page")).toBeNull();
    expect(set.get("q")).toBe("甲");
    expect(set.get("sort")).toBe("price");
    const cleared = writeQuick(set, "alarm", "alarm");
    expect(cleared.get("quick")).toBeNull();
    expect(writeQuick(set, "alarm", "sold_out").get("quick")).toBe("sold_out");
  });
});

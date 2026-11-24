import { makeShop } from "@/test/fixtures";
import { listAttention, summarizeHealth } from "./health-summary";

describe("summarizeHealth", () => {
  it("summarize_health_levels: 有 needs_login 为 error", () => {
    const r = summarizeHealth([makeShop(), makeShop({ id: 2, status: "needs_login", health: "expired" })]);
    expect(r).toEqual({ level: "error", needsLogin: 1, expiring: 0 });
  });
  it("仅 expiring 为 warn", () => {
    const r = summarizeHealth([makeShop(), makeShop({ id: 2, health: "expiring" })]);
    expect(r).toEqual({ level: "warn", needsLogin: 0, expiring: 1 });
  });
  it("needs_login 与 expiring 同时存在时仍为 error，并分别计数", () => {
    const r = summarizeHealth([
      makeShop({ status: "needs_login", health: null }),
      makeShop({ id: 2, health: "expiring" }),
      makeShop({ id: 3, health: "expiring" }),
    ]);
    expect(r).toEqual({ level: "error", needsLogin: 1, expiring: 2 });
  });
  it("全部正常或没有店铺为 ok", () => {
    expect(summarizeHealth([makeShop()]).level).toBe("ok");
    expect(summarizeHealth([]).level).toBe("ok");
  });
  it("已停用的店铺不计入", () => {
    const r = summarizeHealth([makeShop({ status: "disabled", health: "expiring" })]);
    expect(r).toEqual({ level: "ok", needsLogin: 0, expiring: 0 });
  });
});

describe("listAttention", () => {
  it("列出需要处理的店铺，需重新登录在前", () => {
    const rows = listAttention([
      makeShop({ id: 1, name: "甲", health: "expiring" }),
      makeShop({ id: 2, name: "乙", status: "needs_login", health: "expired" }),
      makeShop({ id: 3, name: "丙" }),
      makeShop({ id: 4, name: "丁", status: "disabled", health: "expiring" }),
    ]);
    expect(rows).toEqual([
      { id: 2, name: "乙", kind: "needs_login" },
      { id: 1, name: "甲", kind: "expiring" },
    ]);
  });
});

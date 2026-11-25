import { aggregateAftersaleCounts, deadlineInfo, parseStatus } from "./aftersale-page";

describe("aftersale logic", () => {
  it("状态筛选只接受正整数", () => {
    expect(parseStatus("13")).toBe(13);
    expect(parseStatus(null)).toBeUndefined();
    expect(parseStatus("abc")).toBeUndefined();
    expect(parseStatus("0")).toBeUndefined();
  });

  it("截止时间：已完结 / 超时 / 一天内 / 三天内 / 更远", () => {
    const now = Date.parse("2026-11-25T00:00:00Z");
    expect(deadlineInfo(null, now).text).toBe("已完结");
    expect(deadlineInfo("2026-11-24T00:00:00Z", now)).toEqual({ text: "已超时", tone: "danger" });
    expect(deadlineInfo("2026-11-25T12:00:00Z", now)).toEqual({ text: "剩 12 小时", tone: "danger" });
    expect(deadlineInfo("2026-11-27T00:00:00Z", now)).toEqual({ text: "剩 2 天", tone: "warning" });
    expect(deadlineInfo("2026-11-30T00:00:00Z", now)).toEqual({ text: "剩 5 天", tone: "neutral" });
  });

  it("计数只合计 upstream 的店，失败店单独列出", () => {
    const result = aggregateAftersaleCounts({
      shops: [
        {
          shop_id: 1, source: "upstream", pending_total: 2,
          counts: { all_audit: 1, approaching_deadline_audit: 1 },
          fetched_at: "2026-11-25T00:00:00Z", error: null,
        },
        { shop_id: 2, source: "error", pending_total: 0, counts: null, error: "会话失效" },
      ],
    } as never);
    expect(result.pendingTotal).toBe(2);
    expect(result.auditTotal).toBe(1);
    expect(result.approachingDeadline).toBe(1);
    expect(result.failedShopIds).toEqual([2]);
    expect(result.hasData).toBe(true);
  });
});

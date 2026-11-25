import type { components } from "@/lib/api-types";
import { COUNT_ITEMS, aggregateCounts } from "./aggregate-counts";

type Resp = components["schemas"]["OrderCountsResponse"];
const counts = (n: number) => ({ stock_up: n, exp_ship: n + 1, ship_delay: n + 2, in_aftersale: n + 3 });

describe("aggregateCounts", () => {
  it("aggregate_skips_failed: 只合计 upstream 的店，失败的店单独列出", () => {
    const resp: Resp = {
      shops: [
        { shop_id: 1, source: "upstream", counts: counts(5), fetched_at: "2026-11-25T01:00:00Z" },
        { shop_id: 2, source: "error", error: "会话已过期，请重新扫码登录" },
      ],
    };
    const r = aggregateCounts(resp);
    expect(r.totals.stock_up).toBe(5);
    expect(r.failedShopIds).toEqual([2]);
    expect(r.failures).toEqual([{ shopId: 2, error: "会话已过期，请重新扫码登录" }]);
    expect(r.hasData).toBe(true);
  });

  it("多家成功的店逐项相加", () => {
    const resp: Resp = {
      shops: [
        { shop_id: 1, source: "upstream", counts: counts(1) },
        { shop_id: 2, source: "upstream", counts: counts(10) },
      ],
    };
    expect(aggregateCounts(resp).totals).toEqual({ stock_up: 11, exp_ship: 13, ship_delay: 15, in_aftersale: 17 });
  });

  it("失败的店不能当 0 合计：全部失败时 hasData 为 false", () => {
    const r = aggregateCounts({ shops: [{ shop_id: 1, source: "error", error: "x" }] });
    expect(r.hasData).toBe(false);
    expect(r.failedShopIds).toEqual([1]);
  });

  it("upstream 但没有 counts 的店按失败处理，不当 0", () => {
    const r = aggregateCounts({ shops: [{ shop_id: 3, source: "upstream", counts: null }] });
    expect(r.failedShopIds).toEqual([3]);
    expect(r.hasData).toBe(false);
  });

  it("数据时间取各店中最早的一个（缓存按店 60 秒）", () => {
    const r = aggregateCounts({
      shops: [
        { shop_id: 1, source: "upstream", counts: counts(1), fetched_at: "2026-11-25T01:00:30Z" },
        { shop_id: 2, source: "upstream", counts: counts(1), fetched_at: "2026-11-25T01:00:00Z" },
        { shop_id: 3, source: "upstream", counts: counts(1), fetched_at: null },
      ],
    });
    expect(r.fetchedAt).toBe("2026-11-25T01:00:00Z");
  });

  it("没有任何店铺时为空", () => {
    expect(aggregateCounts({ shops: [] })).toMatchObject({ hasData: false, failedShopIds: [], fetchedAt: null });
  });

  it("计数项为平台口径的四项", () => {
    expect(COUNT_ITEMS.map((i) => i.label)).toEqual(["待发货", "24 小时内须发", "超时未发", "售后中"]);
  });
});

import { aggregateProductCounts, mergeGroups, priceRange, productStateLabel } from "./catalog-page";

const row = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", product_id: "p1", name: "商品", status: "1",
  tab: "onSale", price_lower_cents: 12800, price_higher_cents: 12800, stock_num: 3,
  sell_num: 1, synced_at: "2026-11-25T00:00:00Z",
  display: { img: null, product_url: null, category_name: "类目", quality_score: 4.8, sell_num_30d: 2 },
  ...over,
});

describe("catalog logic", () => {
  it("商品状态缺失显示暂无", () => {
    expect(productStateLabel(row({ tab: null, status: null }) as never)).toBe("暂无");
    expect(productStateLabel(row({ tab: "onSale" }) as never)).toBe("在售");
    expect(productStateLabel(row({ tab: "unpass_new" }) as never)).toBe("未通过");
    expect(productStateLabel(row({ tab: "newTab" }) as never)).toBe("newTab");
    expect(productStateLabel(row({ tab: "已下架" }) as never)).toBe("已下架");
  });

  it("价格区间：同价只显示一个价格，不同价显示区间，缺失显示暂无", () => {
    expect(priceRange(row() as never)).toBe("¥128.00");
    expect(priceRange(row({ price_higher_cents: 9900 }) as never)).toBe("¥99.00 – ¥128.00");
    expect(priceRange(row({ price_lower_cents: null, price_higher_cents: null }) as never)).toBe("暂无");
  });

  it("计数只合计 upstream 的店", () => {
    const result = aggregateProductCounts({
      shops: [
        {
          shop_id: 1, source: "upstream", error: null, fetched_at: "2026-11-25T00:00:00Z",
          counts: { onsale: 6, audit: 0, unpass: 0, draft: 0, forbidden: 0, sell_out_new: 1 },
        },
        { shop_id: 2, source: "error", error: "会话失效", counts: null, fetched_at: null },
      ],
    });
    expect(result.totals.onsale).toBe(6);
    expect(result.totals.sell_out_new).toBe(1);
    expect(result.failedShopIds).toEqual([2]);
    expect(result.hasData).toBe(true);
  });

  it("分组跨店合并，同 ID 只保留一次", () => {
    const groups = mergeGroups({
      shops: [
        { shop_id: 1, source: "upstream", error: null, fetched_at: null,
          items: [{ group_id: "g1", name: "默认" }, { group_id: "g2", name: "清仓" }] },
        { shop_id: 2, source: "upstream", error: null, fetched_at: null,
          items: [{ group_id: "g1", name: "默认" }] },
      ],
    } as never);
    expect(groups.map((g) => g.group_id)).toEqual(["g1", "g2"]);
  });
});

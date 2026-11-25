import { groupWarehouses, stockBadge } from "./stock-page";

const row = (over: Record<string, unknown> = {}) => ({
  id: 1, shop_id: 1, shop_name: "店铺甲", product_id: "p1", name: "商品",
  total_stock_num: 10, spot_stock_num: 8, future_stock_num: 2,
  total_occupied_stock_num: 1, total_unoccupied_stock_num: 9,
  is_alarming: false, synced_at: "2026-11-25T00:00:00Z", ...over,
});

describe("stock logic", () => {
  it("预警优先于售罄", () => {
    expect(stockBadge(row() as never)).toEqual({ label: "正常", tone: "success" });
    expect(stockBadge(row({ total_stock_num: 0 }) as never)).toEqual({ label: "售罄", tone: "warning" });
    expect(stockBadge(row({ is_alarming: true }) as never)).toEqual({ label: "预警", tone: "danger" });
  });

  it("仓库按店分组并带出失败原因", () => {
    const groups = groupWarehouses({
      shops: [
        { shop_id: 1, source: "upstream", error: null, fetched_at: null,
          items: [{ warehouse_id: "w1", name: "主仓" }] },
        { shop_id: 2, source: "error", error: "会话失效", fetched_at: null, items: null },
      ],
    } as never);
    expect(groups[0]).toEqual({
      shopId: 1, items: [{ warehouse_id: "w1", name: "主仓" }], error: null,
    });
    expect(groups[1].error).toBe("会话失效");
  });
});

import type { components } from "@/lib/api-types";
import {
  allSelected,
  canSelect,
  isStage,
  itemSummary,
  pruneSelection,
  toggleAll,
} from "./label-columns";

type LabelOrder = components["schemas"]["LabelOrderRow"];

function row(id: number, blocked: string | null = null): LabelOrder {
  return {
    id,
    shop_id: 1,
    shop_name: "店A",
    order_no: `o${id}`,
    status: "pending_label",
    platform_status: 2,
    combine_id: "c1",
    exception_reason: null,
    amount_cents: 100,
    pay_time: null,
    exp_ship_time: null,
    items: [],
    blocked_reason: blocked,
    waybill: null,
  };
}

describe("label columns", () => {
  it("有阻断原因的订单不可勾选", () => {
    expect(canSelect(row(1))).toBe(true);
    expect(canSelect(row(2, "缺少合单 ID（combine_id）"))).toBe(false);
  });

  it("商品摘要为首个商品名 + 等 N 件", () => {
    const items = [
      { sku_order_id: "s1", product_id: "p1", product_name: "商品甲", sku_spec: null, quantity: 1, price_cents: 100 },
      { sku_order_id: "s2", product_id: "p2", product_name: "商品乙", sku_spec: null, quantity: 1, price_cents: 100 },
    ];
    expect(itemSummary([])).toBe("暂无");
    expect(itemSummary([items[0]])).toBe("商品甲");
    expect(itemSummary(items)).toBe("商品甲 等 2 件");
  });

  it("刷新后保留仍可选中的勾选，移除已失效的", () => {
    const selected = new Set([1, 2, 3]);
    const rows = [row(1), row(2, "已有有效面单")];
    expect([...pruneSelection(selected, rows)]).toEqual([1]);
  });

  it("全选 / 反选只作用于可选行", () => {
    const rows = [row(1), row(2), row(3, "缺少合单 ID（combine_id）")];
    expect(allSelected(new Set([1]), rows)).toBe(false);
    const all = toggleAll(new Set(), rows);
    expect([...all].sort()).toEqual([1, 2]);
    expect(allSelected(all, rows)).toBe(true);
    expect([...toggleAll(all, rows)]).toEqual([]);
  });

  it("阶段", () => {
    expect(isStage("pending")).toBe(true);
    expect(isStage("labeled")).toBe(true);
    expect(isStage(null)).toBe(false);
  });
});

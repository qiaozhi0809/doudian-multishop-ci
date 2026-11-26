import { itemSummary, localStatusBadge, platformStatusText } from "./order-columns";

const item = (name: string | null) => ({
  sku_order_id: null, product_id: null, product_name: name, sku_spec: null, quantity: 1, price_cents: null,
});

describe("itemSummary", () => {
  it("item_summary: 多个商品行显示首个商品名与等 N 件", () => {
    expect(itemSummary([item("商品甲"), item("商品乙"), item("商品丙")])).toBe("商品甲 等 3 件");
  });
  it("一个商品行只显示商品名", () => {
    expect(itemSummary([item("商品甲")])).toBe("商品甲");
  });
  it("没有商品或没有商品名显示暂无", () => {
    expect(itemSummary([])).toBe("暂无");
    expect(itemSummary([item(null)])).toBe("暂无");
    expect(itemSummary([item(null), item("商品乙")])).toBe("暂无 等 2 件");
  });
});

describe("localStatusBadge（ui-guidelines 第 5 节）", () => {
  it.each([
    ["synced", "待处理", "neutral"],
    ["pending_label", "待打单", "neutral"],
    ["label_obtained", "已打单", "info"],
    ["printed", "已打印", "info"],
    ["shipped", "已发货", "success"],
    ["exception", "异常", "danger"],
    ["cancelled", "已取消", "neutral"],
    ["closed", "已关闭", "neutral"],
  ] as const)("%s → %s（%s）", (status, label, tone) => {
    expect(localStatusBadge(status)).toEqual({ label, tone });
  });
});

describe("platformStatusText", () => {
  it("已确认的状态码给出文字，未知保留原始整数", () => {
    expect(platformStatusText(2)).toBe("待发货");
    expect(platformStatusText(3)).toBe("已发货");
    expect(platformStatusText(4)).toBe("已关闭");
    expect(platformStatusText(5)).toBe("已完成");
    expect(platformStatusText(99)).toBe("状态 99");
    expect(platformStatusText(null)).toBe("暂无");
  });
});

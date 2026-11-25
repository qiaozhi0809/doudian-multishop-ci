import { makeShop } from "@/test/fixtures";
import { buildDashboard, shopState, topBars } from "./dashboard";

const baseSources = () => ({
  shops: [makeShop({ id: 1, name: "甲" }), makeShop({ id: 2, name: "乙" })],
  orderCounts: {
    shops: [
      {
        shop_id: 1,
        source: "upstream" as const,
        counts: { stock_up: 5, exp_ship: 2, ship_delay: 1, in_aftersale: 1 },
        fetched_at: "2026-11-25T02:00:00Z",
      },
      { shop_id: 2, source: "error" as const, error: "上游超时" },
    ],
  },
  aftersaleCounts: {
    shops: [
      {
        shop_id: 1,
        source: "upstream",
        counts: { all_audit: 2, approaching_deadline_audit: 1 },
        pending_total: 3,
        fetched_at: "2026-11-25T01:00:00Z",
      },
    ],
  },
  fund: {
    shops: [
      {
        shop_id: 1,
        shop_name: "甲",
        unsettled_amount_cents: 1000,
        unsettled_count: 1,
        margin_balance_cents: 500,
        synced_at: "2026-11-25T00:00:00Z",
      },
    ],
    total_unsettled_amount_cents: 1000,
    total_unsettled_count: 1,
  },
  stock: { total: 3, alarm_count: 2, sold_out_count: 1 },
  products: {
    shops: [
      { shop_id: 1, source: "upstream", counts: { onsale: 9 }, fetched_at: null },
      { shop_id: 2, source: "error", error: "商品接口失败" },
    ],
  },
});

describe("仪表盘聚合", () => {
  it("只合计取到数据的店，失败店单独列出，不当 0 静默合计", () => {
    const model = buildDashboard(baseSources());
    expect(model.kpis).toMatchObject({
      activeShops: 2,
      totalShops: 2,
      stockUp: 5,
      expShip: 2,
      shipDelay: 1,
      aftersalePending: 3,
      unsettledCents: 1000,
      marginCents: 500,
      alarmCount: 2,
      soldOutCount: 1,
      onsaleCount: 9,
    });
    expect(model.orderFailures).toEqual([{ shopId: 2, error: "上游超时" }]);
    expect(model.productFailures).toEqual([{ shopId: 2, error: "商品接口失败" }]);
    expect(model.aftersaleFailures).toEqual([]);
    // 数据时间取各来源里最早的一个（保守）
    expect(model.updatedAt).toBe("2026-11-25T01:00:00Z");
  });

  it("店铺排行按待发货降序，未取到的格子为 null（界面显示暂无）", () => {
    const model = buildDashboard(baseSources());
    expect(model.ranking.map((row) => row.name)).toEqual(["甲", "乙"]);
    expect(model.ranking[0]).toMatchObject({
      shopId: 1,
      stockUp: 5,
      expShip: 2,
      shipDelay: 1,
      aftersalePending: 3,
      onsale: 9,
      unsettledCents: 1000,
      stateText: "正常",
      stateTone: "success",
    });
    expect(model.ranking[1]).toMatchObject({
      stockUp: null,
      aftersalePending: null,
      onsale: null,
      unsettledCents: null,
    });
  });

  it("柱状图取非零值的前 10 家", () => {
    const model = buildDashboard(baseSources());
    expect(model.shipBars).toEqual([{ key: "1", label: "甲", axisLabel: "甲", value: 5 }]);
    expect(model.fundBars).toEqual([{ key: "1", label: "甲", axisLabel: "甲", value: 1000 }]);
  });

  it("没有任何数据源时给出零值，不抛错", () => {
    const model = buildDashboard({ shops: [] });
    expect(model.kpis).toMatchObject({ activeShops: 0, totalShops: 0, stockUp: 0, aftersalePending: 0 });
    expect(model.ranking).toEqual([]);
    expect(model.shipBars).toEqual([]);
    expect(model.updatedAt).toBeNull();
  });
});

describe("店铺会话状态", () => {
  it("按 ui-guidelines 第 5 节的文案与色调", () => {
    expect(shopState(makeShop())).toEqual({ text: "正常", tone: "success" });
    expect(shopState(makeShop({ status: "disabled" }))).toEqual({ text: "已停用", tone: "neutral" });
    expect(shopState(makeShop({ status: "needs_login", health: null }))).toEqual({
      text: "需重新登录",
      tone: "danger",
    });
    expect(shopState(makeShop({ paused_reason: "risk_blocked:1" }))).toEqual({
      text: "风控暂停",
      tone: "danger",
    });
    expect(shopState(makeShop({ egress_status: "unreachable" }))).toEqual({ text: "出口异常", tone: "danger" });
    expect(shopState(makeShop({ egress_status: "changed" }))).toEqual({ text: "出口待确认", tone: "warning" });
    expect(shopState(makeShop({ health: "expiring" }))).toEqual({ text: "即将过期", tone: "warning" });
  });
});

describe("topBars", () => {
  const rows = [
    { shopId: 1, name: "甲", value: 0 },
    { shopId: 2, name: "乙", value: 3 },
    { shopId: 3, name: "丙", value: 7 },
    { shopId: 4, name: "丁", value: null },
  ];

  it("过滤零与空值，按值降序，可限制条数", () => {
    expect(topBars(rows, (row) => row.value)).toEqual([
      { key: "3", label: "丙", axisLabel: "丙", value: 7 },
      { key: "2", label: "乙", axisLabel: "乙", value: 3 },
    ]);
    expect(topBars(rows, (row) => row.value, 1)).toHaveLength(1);
  });

  it("长店铺名在轴上截断，完整名称保留在标签里", () => {
    const bars = topBars([{ shopId: 9, name: "一二三四五六七", value: 2 }], (row) => row.value);
    expect(bars[0]).toMatchObject({ label: "一二三四五六七", axisLabel: "一二三四五…" });
  });
});

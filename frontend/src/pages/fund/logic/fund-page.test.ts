import {
  billAmountText,
  billSummary,
  hasPendingAmount,
  marginLevelText,
  parseBillDays,
  settledMarginTotal,
  settlementDelayText,
  type BillItem,
} from "./fund-page";

const item = (over: Partial<BillItem> = {}): BillItem => ({
  amount_cents: 0,
  amount_status: "pending",
  amount_field: null,
  raw: {},
  ...over,
});

describe("fund logic", () => {
  it("账单金额：未校准显示待探明，已校准按分换算", () => {
    expect(billAmountText(item())).toBe("待探明");
    expect(billAmountText(item({ amount_cents: 1234, amount_status: "confirmed" }))).toBe("¥12.34");
  });

  it("账单摘要优先平台文案，其次单号，最后 —", () => {
    expect(billSummary(item({ raw: { bill_type_text: "技术服务费", bill_no: "B1" } }))).toBe("技术服务费");
    expect(billSummary(item({ raw: { bill_no: "B1" } }))).toBe("B1");
    expect(billSummary(item())).toBe("—");
  });

  it("存在未校准金额时给出提示标记", () => {
    expect(hasPendingAmount([{ shop_id: 1, source: "upstream", total: 1, items: [item()], error: null, fetched_at: null }])).toBe(true);
    expect(
      hasPendingAmount([{ shop_id: 1, source: "upstream", total: 0, items: [], error: null, fetched_at: null }]),
    ).toBe(false);
  });

  it("保证金等级与结算周期文案", () => {
    expect(marginLevelText("low")).toBe("低");
    expect(marginLevelText("weird")).toBe("weird");
    expect(marginLevelText(null)).toBe("暂无");
    expect(settlementDelayText(21)).toBe("确认收货 / 核销后 21 天结算");
    expect(settlementDelayText(null)).toBe("结算周期待探明");
  });

  it("保证金余额只合计已同步的店铺", () => {
    const total = settledMarginTotal({
      shops: [
        { shop_id: 1, shop_name: "A", unsettled_amount_cents: 0, unsettled_count: 0, margin_balance_cents: 1000 },
        { shop_id: 2, shop_name: "B", unsettled_amount_cents: 0, unsettled_count: 0, margin_balance_cents: null },
      ],
      total_unsettled_amount_cents: 0,
      total_unsettled_count: 0,
    } as never);
    expect(total).toBe(1000);
  });

  it("账单天数只接受 7 / 30", () => {
    expect(parseBillDays("7")).toBe(7);
    expect(parseBillDays("30")).toBe(30);
    expect(parseBillDays("999")).toBe(30);
    expect(parseBillDays(null)).toBe(30);
  });
});

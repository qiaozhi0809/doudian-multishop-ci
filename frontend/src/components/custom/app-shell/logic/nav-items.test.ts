import { FOOTER_NAV, NAV_ITEMS, NAV_SECTIONS, pageTitle } from "./nav-items";

describe("导航分组（frontend.md 1.1）", () => {
  it("一级结构为仪表盘、订单处理、售后、商品与库存、财务，底部是店铺与设置", () => {
    expect(
      NAV_SECTIONS.map((section) => (section.kind === "link" ? section.item.label : section.label)),
    ).toEqual(["仪表盘", "订单处理", "售后", "商品与库存", "财务"]);
    expect(FOOTER_NAV.map((item) => item.label)).toEqual(["店铺与设置"]);
  });

  it("订单处理组按流水线排列：订单 → 打单台 → 发货台", () => {
    const group = NAV_SECTIONS.find((section) => section.kind === "group" && section.id === "orders");
    expect(group && group.kind === "group" ? group.items.map((item) => item.label) : []).toEqual([
      "订单",
      "打单台",
      "发货台",
    ]);
  });

  it("补上仪表盘、发货台、对账三个入口", () => {
    const paths = NAV_ITEMS.map((item) => item.path);
    expect(paths).toEqual(expect.arrayContaining(["/dashboard", "/shipping", "/reconcile"]));
  });

  it("pageTitle 按路径给出页面标题（含子路径）", () => {
    expect(pageTitle("/dashboard")).toBe("仪表盘");
    expect(pageTitle("/orders")).toBe("订单");
    expect(pageTitle("/labeling")).toBe("打单台");
    expect(pageTitle("/shipping")).toBe("发货台");
    expect(pageTitle("/reconcile")).toBe("对账");
    expect(pageTitle("/aftersale")).toBe("售后工作台");
    expect(pageTitle("/catalog")).toBe("商品");
    expect(pageTitle("/stock")).toBe("库存");
    expect(pageTitle("/fund")).toBe("资金");
    expect(pageTitle("/shops")).toBe("店铺与设置");
    expect(pageTitle("/shops/1")).toBe("店铺与设置");
    expect(pageTitle("/unknown")).toBe("");
  });

});

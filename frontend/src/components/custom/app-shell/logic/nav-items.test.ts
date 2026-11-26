import { FOOTER_NAV, NAV_ITEMS, NAV_SECTIONS, pageTitle } from "./nav-items";

describe("导航分组（frontend.md 1.1）", () => {
  it("一级结构为概览、订单、客服、商品、资金，底部是店铺管理", () => {
    expect(
      NAV_SECTIONS.map((section) => (section.kind === "link" ? section.item.label : section.label)),
    ).toEqual(["概览", "订单", "客服", "商品", "资金"]);
    expect(FOOTER_NAV.map((item) => item.label)).toEqual(["店铺管理", "代理池"]);
  });

  it("订单组按流水线排列：全部订单 → 打单发货 → 售后处理 → 发货异常", () => {
    const group = NAV_SECTIONS.find((section) => section.kind === "group" && section.id === "orders");
    expect(group && group.kind === "group" ? group.items.map((item) => item.label) : []).toEqual([
      "全部订单",
      "打单发货",
      "售后处理",
      "发货异常",
    ]);
  });

  it("客服组紧跟订单组，只有「消息」一项", () => {
    const index = NAV_SECTIONS.findIndex((section) => section.kind === "group" && section.id === "orders");
    expect(NAV_SECTIONS[index + 1]).toMatchObject({
      kind: "group",
      id: "service",
      label: "客服",
      items: [{ path: "/messages", label: "消息" }],
    });
    expect(pageTitle("/messages")).toBe("消息");
  });

  it("发货台已并入打单发货，导航里不再有单独入口", () => {
    const paths = NAV_ITEMS.map((item) => item.path);
    expect(paths).toEqual(expect.arrayContaining(["/dashboard", "/labeling", "/reconcile"]));
    expect(paths).not.toContain("/shipping");
  });

  it("pageTitle 按路径给出页面标题（含子路径）", () => {
    expect(pageTitle("/dashboard")).toBe("概览");
    expect(pageTitle("/orders")).toBe("全部订单");
    expect(pageTitle("/labeling")).toBe("打单发货");
    expect(pageTitle("/reconcile")).toBe("发货异常");
    expect(pageTitle("/aftersale")).toBe("售后处理");
    expect(pageTitle("/catalog")).toBe("商品列表");
    expect(pageTitle("/stock")).toBe("库存");
    expect(pageTitle("/fund")).toBe("结算与保证金");
    expect(pageTitle("/shops")).toBe("店铺管理");
    expect(pageTitle("/shops/1")).toBe("店铺管理");
    expect(pageTitle("/proxy-pool")).toBe("代理池");
    expect(pageTitle("/unknown")).toBe("");
  });
});

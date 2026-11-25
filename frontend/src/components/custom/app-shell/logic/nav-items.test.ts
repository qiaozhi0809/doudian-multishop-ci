import { NAV_ITEMS, pageTitle } from "./nav-items";

describe("nav", () => {
  it("菜单为订单、打单台、店铺与设置", () => {
    expect(NAV_ITEMS.map((i) => i.label)).toEqual(["订单", "打单台", "店铺与设置"]);
  });
  it("pageTitle 按路径给出页面标题", () => {
    expect(pageTitle("/orders")).toBe("订单");
    expect(pageTitle("/labeling")).toBe("打单台");
    expect(pageTitle("/shops")).toBe("店铺与设置");
    expect(pageTitle("/shops/1")).toBe("店铺与设置");
    expect(pageTitle("/unknown")).toBe("");
  });
});

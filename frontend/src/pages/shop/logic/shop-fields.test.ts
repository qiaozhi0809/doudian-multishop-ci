import { bankNameError, bankTailError, buildShopPatch, platformShopIdError } from "./shop-fields";
import { makeShop } from "@/test/fixtures";

describe("店铺字段校验", () => {
  it("店铺ID：空值放行，1–20 位数字通过，其他报错", () => {
    expect(platformShopIdError("")).toBeUndefined();
    expect(platformShopIdError("100000001")).toBeUndefined();
    expect(platformShopIdError("1".repeat(21))).toBe("店铺ID是 1 到 20 位数字");
    expect(platformShopIdError("12a")).toBe("店铺ID是 1 到 20 位数字");
  });

  it("卡号尾号：空值放行，4 位数字通过，其他报错", () => {
    expect(bankTailError("")).toBeUndefined();
    expect(bankTailError("0000")).toBeUndefined();
    expect(bankTailError("123")).toBe("卡号尾号是 4 位数字");
  });
});

describe("全角数字与开户行长度（与后端一致）", () => {
  it("全角数字不算数字", () => {
    expect(platformShopIdError("１２３")).toBe("店铺ID是 1 到 20 位数字");
    expect(bankTailError("１２３４")).toBe("卡号尾号是 4 位数字");
  });
  it("开户行不超过 50 个字", () => {
    expect(bankNameError("示".repeat(50))).toBeUndefined();
    expect(bankNameError("示".repeat(51))).toBe("开户行不超过 50 个字");
  });
});

describe("buildShopPatch", () => {
  it("只带有改动的字段：旧的不合规数据不改就不发送", () => {
    const shop = makeShop({ name: "店A", entity: null, platform_shop_id: null, bank_name: "示".repeat(60), bank_tail: "**** 1234" });
    const values = { name: "店A 改", entity: "", platformShopId: "", bankName: "示".repeat(60), bankTail: "**** 1234" };
    expect(buildShopPatch(shop, values)).toEqual({ name: "店A 改" });
  });
  it("清空发 null，未改动时为空对象", () => {
    const shop = makeShop({ name: "店A", entity: "某主体", bank_tail: "0001" });
    expect(buildShopPatch(shop, { name: "店A", entity: "", platformShopId: shop.platform_shop_id ?? "", bankName: shop.bank_name ?? "", bankTail: "0001" })).toEqual({ entity: null });
    expect(buildShopPatch(shop, { name: "店A", entity: "某主体", platformShopId: shop.platform_shop_id ?? "", bankName: shop.bank_name ?? "", bankTail: "0001" })).toEqual({});
  });
});

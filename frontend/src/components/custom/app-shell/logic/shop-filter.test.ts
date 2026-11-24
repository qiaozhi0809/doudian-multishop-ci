import { parseShopFilter, serializeShopFilter, withShopFilter } from "./shop-filter";

describe("parseShopFilter", () => {
  it("parse_shop_filter: 逗号分隔的数字", () => {
    expect(parseShopFilter("?shops=1,2")).toEqual([1, 2]);
    expect(parseShopFilter("shops=1,2")).toEqual([1, 2]);
  });
  it("空 = 全部", () => {
    expect(parseShopFilter("")).toEqual([]);
    expect(parseShopFilter("?page=2")).toEqual([]);
    expect(parseShopFilter("?shops=")).toEqual([]);
  });
  it("忽略非数字，保留合法项", () => {
    expect(parseShopFilter("?shops=a,3")).toEqual([3]);
  });
  it("忽略 0、负数、小数与多余逗号，并去重", () => {
    expect(parseShopFilter("?shops=0,-1,1.5,,2,2,")).toEqual([2]);
  });
  it("与其他参数并存", () => {
    expect(parseShopFilter("?status=shipped&shops=4&page=2")).toEqual([4]);
  });
});

describe("serializeShopFilter", () => {
  it("升序、去重、逗号连接，空为空串", () => {
    expect(serializeShopFilter([3, 1, 3])).toBe("1,3");
    expect(serializeShopFilter([])).toBe("");
  });
  it("往返一致", () => {
    expect(parseShopFilter(`?shops=${serializeShopFilter([5, 2])}`)).toEqual([2, 5]);
  });
});

describe("withShopFilter", () => {
  it("给路径带上店铺筛选，空筛选不带参数", () => {
    expect(withShopFilter("/orders", [2, 1])).toBe("/orders?shops=1,2");
    expect(withShopFilter("/shops", [])).toBe("/shops");
  });
});

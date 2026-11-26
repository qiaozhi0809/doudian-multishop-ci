import type { components } from "./api-types";
import { shopsWithOpenProblems, withoutShops } from "./open-problem-shops";

type StrongOpenShop = components["schemas"]["StrongOpenShop"];

const shop = (id: number, kinds: StrongOpenShop["kinds"]): StrongOpenShop => ({
  shop_id: id, shop_name: `示例店${id}`, kinds, link: null, problems: kinds.map((kind) => ({ kind, link: null })),
});

describe("shopsWithOpenProblems", () => {
  it("登录、出口、风控问题的店算在内，只有临近发货超时的店不算", () => {
    const set = shopsWithOpenProblems([
      shop(1, ["login_expired"]),
      shop(2, ["egress_unreachable"]),
      shop(3, ["egress_changed"]),
      shop(4, ["egress_duplicate"]),
      shop(5, ["risk_paused"]),
      shop(6, ["ship_deadline"]),
      shop(7, ["ship_deadline", "risk_paused"]),
    ]);
    expect([...set].sort()).toEqual([1, 2, 3, 4, 5, 7]);
  });
});

describe("withoutShops", () => {
  it("去掉已在横条的店，其余原样保留", () => {
    const failures = [{ shopId: 1, error: "登录失效" }, { shopId: 2, error: "接口报错" }];
    expect(withoutShops(failures, new Set([1]))).toEqual([{ shopId: 2, error: "接口报错" }]);
    expect(withoutShops(failures, new Set())).toEqual(failures);
  });
});

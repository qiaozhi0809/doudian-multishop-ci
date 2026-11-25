import type { components } from "@/lib/api-types";
import { availablePoolItems, poolOptionLabel } from "./available-pool";

type PoolItem = components["schemas"]["PoolItem"];

const item = (over: Partial<PoolItem> = {}): PoolItem => ({
  id: 1,
  proxy_display: "1.2.3.4:8080",
  expires_at: "2026-12-31",
  expiry_state: "ok",
  in_use_by: null,
  last_checked_at: null,
  last_check_ip: null,
  ...over,
});

describe("availablePoolItems", () => {
  it("过滤掉被占用的和已过期的，保留临近到期与不限期的", () => {
    const items = [
      item({ id: 1 }),
      item({ id: 2, in_use_by: { shop_id: 3, shop_name: "店A" } }),
      item({ id: 3, expiry_state: "expired" }),
      item({ id: 4, expiry_state: "expiring" }),
      item({ id: 5, expires_at: null }),
    ];
    expect(availablePoolItems(items).map((i) => i.id)).toEqual([1, 4, 5]);
  });
});

describe("poolOptionLabel", () => {
  it("显示月-日；无到期日显示不限期", () => {
    expect(poolOptionLabel(item())).toBe("1.2.3.4:8080 · 到期 12-31");
    expect(poolOptionLabel(item({ expires_at: null }))).toBe("1.2.3.4:8080 · 不限期");
  });
});

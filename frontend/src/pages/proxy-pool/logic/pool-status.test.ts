import type { components } from "@/lib/api-types";
import { sortRows } from "@/lib/list-sort";
import { checkNotice, checkReasonText, poolStatus, poolStatusSortValue } from "./pool-status";

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

describe("poolStatus", () => {
  it("空闲 success", () => {
    expect(poolStatus(item())).toEqual({ label: "空闲", tone: "success" });
  });
  it("被占用 info，文案带店铺名", () => {
    expect(poolStatus(item({ in_use_by: { shop_id: 3, shop_name: "店A" } }))).toEqual({ label: "已用于「店A」", tone: "info" });
  });
  it("过期且占用 danger", () => {
    const r = poolStatus(item({ expiry_state: "expired", in_use_by: { shop_id: 3, shop_name: "店A" } }));
    expect(r).toEqual({ label: "已过期", tone: "danger" });
  });
  it("过期空闲 muted", () => {
    expect(poolStatus(item({ expiry_state: "expired" }))).toEqual({ label: "已过期", tone: "muted" });
  });
  it("即将到期但未过期仍按占用情况显示", () => {
    expect(poolStatus(item({ expiry_state: "expiring" })).label).toBe("空闲");
  });
});

describe("checkReasonText", () => {
  it("四种原因", () => {
    expect(checkReasonText("timeout")).toBe("检查超时（10 秒）");
    expect(checkReasonText("proxy_unavailable")).toBe("代理连不上，请检查地址、账号密码或是否到期");
    expect(checkReasonText("network")).toBe("网络错误，请稍后重试");
    expect(checkReasonText("bad_echo")).toBe("回显地址返回的不是 IP，请检查设置里的回显地址");
  });
  it("null 返回空串", () => {
    expect(checkReasonText(null)).toBe("");
  });
});

describe("checkNotice", () => {
  const ok = { elapsed_ms: 80, ip: "9.9.9.9", ip_in_use_by: null, reason: null } as const;
  it("通过：写「检查通过」与出口 IP", () => {
    expect(checkNotice("1.2.3.4:80", ok)).toEqual({ tone: "success", text: "1.2.3.4:80：检查通过，出口 IP 9.9.9.9（80 ms）" });
  });
  it("IP 已被别的店使用：一句话里用逗号接上，不用句号", () => {
    expect(checkNotice("1.2.3.4:80", { ...ok, ip_in_use_by: { shop_id: 4, shop_name: "店B" } }).text).toBe(
      "1.2.3.4:80：检查通过，出口 IP 9.9.9.9（80 ms），该 IP 已被店铺「店B」使用",
    );
  });
  it("失败：没有原因时写「检查失败」", () => {
    expect(checkNotice("1.2.3.4:80", { ...ok, ip: null })).toEqual({ tone: "danger", text: "1.2.3.4:80：检查失败" });
  });
});

describe("poolStatusSortValue", () => {
  it("按显示的状态排：空闲 → 已用于（按店名）→ 已过期，不按 expiry_state 原始码", () => {
    const rows = [
      item({ id: 1, expiry_state: "expired" }),
      item({ id: 2, in_use_by: { shop_id: 2, shop_name: "乙店" } as never }),
      item({ id: 3, expiry_state: "expiring" }),
      item({ id: 4, expiry_state: "expiring", in_use_by: { shop_id: 1, shop_name: "甲店" } as never }),
    ];
    const sorted = sortRows(rows, { key: "expiry_state", direction: "asc" }, (row) => poolStatusSortValue(row));
    expect(sorted.map((r) => poolStatus(r).label)).toEqual(["空闲", "已用于「甲店」", "已用于「乙店」", "已过期"]);
  });
});

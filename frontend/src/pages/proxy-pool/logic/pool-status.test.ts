import type { components } from "@/lib/api-types";
import { checkReasonText, poolStatus } from "./pool-status";

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
    expect(checkReasonText("timeout")).toBe("检测超时（10 秒）");
    expect(checkReasonText("proxy_unavailable")).toBe("代理连不上，请检查地址、账号密码或是否到期");
    expect(checkReasonText("network")).toBe("网络错误，请稍后重试");
    expect(checkReasonText("bad_echo")).toBe("回显地址返回的不是 IP，请检查设置里的回显地址");
  });
  it("null 返回空串", () => {
    expect(checkReasonText(null)).toBe("");
  });
});

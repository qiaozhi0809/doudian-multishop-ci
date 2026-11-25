import { makeShop } from "@/test/fixtures";
import {
  canScan,
  egressBadge,
  egressModeLabel,
  pausedBadge,
  primaryAction,
  readyBadge,
  scanBlockedReason,
  scanDisabledReason,
  shopStatusBadge,
} from "./shop-status";

const NOW = new Date("2026-11-25T00:00:00Z");
const daysFromNow = (d: number) => new Date(NOW.getTime() + d * 86_400_000).toISOString();

describe("shopStatusBadge", () => {
  it("active + healthy 为正常", () => {
    expect(shopStatusBadge(makeShop(), NOW)).toEqual({ label: "正常", tone: "success" });
  });
  it("badge_expiring_days: 3 天后过期 → 剩 3 天、warning", () => {
    const b = shopStatusBadge(makeShop({ health: "expiring", expires_at: daysFromNow(3) }), NOW);
    expect(b.label).toContain("剩 3 天");
    expect(b.label).toBe("即将过期（剩 3 天）");
    expect(b.tone).toBe("warning");
  });
  it("即将过期但没有到期时间时不带天数", () => {
    expect(shopStatusBadge(makeShop({ health: "expiring", expires_at: null }), NOW).label).toBe("即将过期");
  });
  it("badge_needs_login: danger", () => {
    expect(shopStatusBadge(makeShop({ status: "needs_login", health: "expired" }), NOW)).toEqual({
      label: "需重新登录",
      tone: "danger",
    });
  });
  it("disabled 为已停用、neutral", () => {
    expect(shopStatusBadge(makeShop({ status: "disabled" }), NOW)).toEqual({ label: "已停用", tone: "neutral" });
  });
});

describe("egressBadge", () => {
  it.each([
    ["unchecked", "未检查", "neutral"],
    ["unreachable", "出口不通", "danger"],
  ] as const)("%s → %s", (egress_status, label, tone) => {
    expect(egressBadge(makeShop({ egress_status }), NOW)).toEqual({ label, tone });
  });
  it("ok 显示出口 IP", () => {
    expect(egressBadge(makeShop({ egress_status: "ok", egress_ip: "1.2.3.4" }), NOW)).toEqual({
      label: "出口正常 · 1.2.3.4",
      tone: "success",
    });
  });
  it("changed 显示待确认的新 IP、warning", () => {
    expect(egressBadge(makeShop({ egress_status: "changed", egress_ip_pending: "1.2.3.5" }), NOW)).toEqual({
      label: "出口 IP 已变为 1.2.3.5，需确认",
      tone: "warning",
    });
  });
  it("egress_badge_duplicate: danger，文案含重复", () => {
    const b = egressBadge(makeShop({ egress_status: "duplicate" }), NOW);
    expect(b.tone).toBe("danger");
    expect(b.label).toContain("重复");
  });
  it("未设置出口方式时显示未设置出口", () => {
    expect(egressBadge(makeShop({ egress_mode: null, egress_status: "unchecked" }), NOW)).toEqual({
      label: "未设置出口",
      tone: "neutral",
    });
  });
  it("代理 7 天内到期时追加提示，出口正常降为 warning", () => {
    const b = egressBadge(makeShop({ egress_status: "ok", egress_ip: "1.2.3.4", proxy_expires_at: daysFromNow(5) }), NOW);
    expect(b).toEqual({ label: "出口正常 · 1.2.3.4，代理 5 天后到期", tone: "warning" });
  });
  it("代理 8 天后到期不追加", () => {
    const b = egressBadge(makeShop({ egress_status: "ok", egress_ip: "1.2.3.4", proxy_expires_at: daysFromNow(8) }), NOW);
    expect(b.label).toBe("出口正常 · 1.2.3.4");
  });
  it("代理已到期追加已到期，色调 danger", () => {
    const b = egressBadge(makeShop({ egress_status: "ok", egress_ip: "1.2.3.4", proxy_expires_at: daysFromNow(-1) }), NOW);
    expect(b).toEqual({ label: "出口正常 · 1.2.3.4，代理已到期", tone: "danger" });
  });
  it("直连没有代理到期提示", () => {
    const b = egressBadge(makeShop({ egress_mode: "direct", egress_status: "ok", egress_ip: "1.2.3.4", proxy_expires_at: null }), NOW);
    expect(b.label).toBe("出口正常 · 1.2.3.4");
  });
});

describe("pausedBadge", () => {
  it("paused_shows_resume: paused_reason 非空时显示风控暂停，并带原因码", () => {
    expect(pausedBadge(makeShop({ paused_reason: "risk_blocked:602502151" }))).toEqual({
      label: "风控暂停",
      reason: "risk_blocked:602502151",
    });
  });
  it("未暂停为 null", () => {
    expect(pausedBadge(makeShop({ paused_reason: null }))).toBeNull();
  });
});

describe("canScan", () => {
  it("can_scan_requires_ok_egress: 只有 ok 才能扫码", () => {
    expect(canScan(makeShop({ egress_status: "ok" }))).toBe(true);
    for (const s of ["unchecked", "unreachable", "changed", "duplicate"] as const) {
      expect(canScan(makeShop({ egress_status: s }))).toBe(false);
    }
  });
  it("未配置出口方式不能扫码", () => {
    expect(canScan(makeShop({ egress_mode: null, egress_status: "ok" }))).toBe(false);
  });
});

describe("scanBlockedReason", () => {
  it("能扫码时为 null", () => {
    expect(scanBlockedReason(makeShop())).toBeNull();
  });
  it("给出原因与下一步", () => {
    expect(scanBlockedReason(makeShop({ egress_mode: null, egress_status: "unchecked" }))).toBe("还没有设置出口，请先设置出口");
    expect(scanBlockedReason(makeShop({ egress_status: "unchecked" }))).toBe("出口未检查通过，不能扫码");
    expect(scanBlockedReason(makeShop({ egress_status: "unreachable" }))).toBe("出口不通，请检查代理是否到期或更换代理");
    expect(scanBlockedReason(makeShop({ egress_status: "changed" }))).toBe("出口 IP 已变化，请先确认新 IP");
    expect(scanBlockedReason(makeShop({ egress_status: "duplicate" }))).toBe("出口 IP 与其他店重复，请更换出口");
  });
});

describe("readyBadge / egressModeLabel", () => {
  it("取号就绪：是为就绪；否时带原因", () => {
    expect(readyBadge(makeShop())).toEqual({ label: "就绪", tone: "success", detail: null });
    expect(readyBadge(makeShop({ ready_for_label: false, not_ready_reasons: ["缺少默认发货地址", "没有面单账户"] }))).toEqual({
      label: "未就绪",
      tone: "neutral",
      detail: "缺少默认发货地址；没有面单账户",
    });
  });
  it("出口方式文案", () => {
    expect(egressModeLabel(makeShop({ egress_mode: "direct" }))).toBe("直连");
    expect(egressModeLabel(makeShop({ egress_mode: "proxy" }))).toBe("代理");
    expect(egressModeLabel(makeShop({ egress_mode: null }))).toBe("未设置");
  });
});

describe("scanDisabledReason（按钮禁用说明）", () => {
  it("正常时为 null", () => {
    expect(scanDisabledReason(makeShop())).toBeNull();
  });
  it("已停用、风控暂停优先于出口问题", () => {
    expect(scanDisabledReason(makeShop({ status: "disabled", egress_status: "unreachable" }))).toBe("店铺已停用，不能扫码");
    expect(scanDisabledReason(makeShop({ paused_reason: "risk_blocked:1", egress_status: "unreachable" }))).toBe(
      "风控暂停中，请先恢复",
    );
  });
  it("其余沿用出口原因", () => {
    expect(scanDisabledReason(makeShop({ egress_status: "unchecked" }))).toBe("出口未检查通过，不能扫码");
  });
});

describe("primaryAction（行内直接显示的主操作）", () => {
  it("还没有设置出口：先设置出口", () => {
    expect(primaryAction(makeShop({ egress_mode: null, egress_status: "unchecked" }))).toBe("set-egress");
  });
  it("出口未检查（以及不通、重复、已变化）：先检查出口，不显示扫码", () => {
    for (const s of ["unchecked", "unreachable", "duplicate", "changed"] as const) {
      expect(primaryAction(makeShop({ egress_status: s }))).toBe("check-egress");
    }
  });
  it("出口检查通过：扫码登录", () => {
    expect(primaryAction(makeShop({ egress_status: "ok" }))).toBe("login");
  });
  it("已停用或风控暂停但出口正常：仍显示扫码登录（禁用并说明原因）", () => {
    expect(primaryAction(makeShop({ status: "disabled" }))).toBe("login");
    expect(primaryAction(makeShop({ paused_reason: "risk_blocked:1" }))).toBe("login");
  });
});

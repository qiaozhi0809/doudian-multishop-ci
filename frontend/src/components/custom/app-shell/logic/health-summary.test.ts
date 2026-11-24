import { makeShop } from "@/test/fixtures";
import { listAttention, summarizeHealth } from "./health-summary";

const NOW = new Date("2026-11-25T00:00:00Z");
const daysFromNow = (d: number) => new Date(NOW.getTime() + d * 86_400_000).toISOString();

describe("summarizeHealth", () => {
  it("summarize_health_levels: needs_login 为 error", () => {
    const r = summarizeHealth([makeShop(), makeShop({ id: 2, status: "needs_login", health: "expired" })], NOW);
    expect(r).toMatchObject({ level: "error", errorCount: 1, warnCount: 0 });
  });
  it("风控暂停为 error", () => {
    const r = summarizeHealth([makeShop({ paused_reason: "risk_blocked:602502151" })], NOW);
    expect(r).toMatchObject({ level: "error", errorCount: 1 });
  });
  it.each(["unreachable", "changed", "duplicate"] as const)("出口 %s 为 error", (egress_status) => {
    expect(summarizeHealth([makeShop({ egress_status })], NOW)).toMatchObject({ level: "error", errorCount: 1 });
  });
  it("出口未检查不算异常", () => {
    expect(summarizeHealth([makeShop({ egress_status: "unchecked" })], NOW).level).toBe("ok");
  });
  it("会话即将过期为 warn", () => {
    const r = summarizeHealth([makeShop(), makeShop({ id: 2, health: "expiring", expires_at: daysFromNow(3) })], NOW);
    expect(r).toMatchObject({ level: "warn", errorCount: 0, warnCount: 1 });
  });
  it("代理 7 天内到期为 warn，8 天不算", () => {
    expect(summarizeHealth([makeShop({ proxy_expires_at: daysFromNow(7) })], NOW).level).toBe("warn");
    expect(summarizeHealth([makeShop({ proxy_expires_at: daysFromNow(8) })], NOW).level).toBe("ok");
  });
  it("error 与 warn 同时存在时为 error，并分别计数（一家店只算一次）", () => {
    const r = summarizeHealth(
      [
        makeShop({ id: 1, status: "needs_login", health: null, proxy_expires_at: daysFromNow(2) }),
        makeShop({ id: 2, health: "expiring", expires_at: daysFromNow(2) }),
        makeShop({ id: 3, proxy_expires_at: daysFromNow(1) }),
      ],
      NOW,
    );
    expect(r).toMatchObject({ level: "error", errorCount: 1, warnCount: 2 });
  });
  it("全部正常为 ok", () => {
    expect(summarizeHealth([makeShop()], NOW)).toMatchObject({ level: "ok", errorCount: 0, warnCount: 0 });
  });
  it("没有任何店铺为 empty", () => {
    expect(summarizeHealth([], NOW).level).toBe("empty");
  });
  it("已停用的店铺不计入问题", () => {
    const r = summarizeHealth(
      [makeShop({ status: "disabled", health: "expiring", paused_reason: "x", egress_status: "duplicate" })],
      NOW,
    );
    expect(r).toMatchObject({ level: "ok", errorCount: 0, warnCount: 0 });
  });
});

describe("listAttention", () => {
  const rowFor = (overrides: Parameters<typeof makeShop>[0]) => listAttention([makeShop(overrides)], NOW)[0];

  it("文案与色调按 ui-guidelines 第 5 节", () => {
    expect(rowFor({ status: "needs_login", health: null })).toMatchObject({ label: "需重新登录", tone: "danger" });
    expect(rowFor({ paused_reason: "risk_blocked:1" })).toMatchObject({ label: "风控暂停", tone: "danger" });
    expect(rowFor({ egress_status: "unreachable" })).toMatchObject({ label: "出口不通", tone: "danger" });
    expect(rowFor({ egress_status: "duplicate" })).toMatchObject({ label: "出口 IP 与其他店重复", tone: "danger" });
    expect(rowFor({ egress_status: "changed", egress_ip_pending: "1.2.3.5" })).toMatchObject({
      label: "出口 IP 已变为 1.2.3.5，需确认",
      tone: "warning",
    });
    expect(rowFor({ egress_status: "changed", egress_ip_pending: null }).label).toBe("出口 IP 已变化，需确认");
    expect(rowFor({ health: "expiring", expires_at: daysFromNow(3) })).toMatchObject({
      label: "即将过期（剩 3 天）",
      tone: "warning",
    });
    expect(rowFor({ proxy_expires_at: daysFromNow(5) })).toMatchObject({ label: "代理 5 天后到期", tone: "warning" });
  });

  it("出口 IP 已变化：色调为 warning（guidelines 第 5 节），但计入需处理", () => {
    const shops = [makeShop({ egress_status: "changed", egress_ip_pending: "1.2.3.5" })];
    expect(listAttention(shops, NOW)[0]).toMatchObject({ tone: "warning", severity: "error" });
    expect(summarizeHealth(shops, NOW).level).toBe("error");
  });

  it("多个问题只显示最严重的一个", () => {
    const row = rowFor({
      status: "needs_login",
      health: null,
      paused_reason: "risk_blocked:1",
      egress_status: "duplicate",
      proxy_expires_at: daysFromNow(2),
    });
    expect(row.label).toBe("需重新登录");
    expect(rowFor({ paused_reason: "x", egress_status: "unreachable" }).label).toBe("风控暂停");
    expect(rowFor({ egress_status: "unreachable", proxy_expires_at: daysFromNow(2) }).label).toBe("出口不通");
    expect(rowFor({ health: "expiring", expires_at: daysFromNow(2), proxy_expires_at: daysFromNow(1) }).label).toBe(
      "即将过期（剩 2 天）",
    );
  });

  it("error 在前、warn 在后，已停用与正常店铺不列出", () => {
    const rows = listAttention(
      [
        makeShop({ id: 1, name: "甲", health: "expiring", expires_at: daysFromNow(2) }),
        makeShop({ id: 2, name: "乙", status: "needs_login", health: "expired" }),
        makeShop({ id: 3, name: "丙" }),
        makeShop({ id: 4, name: "丁", status: "disabled", health: "expiring" }),
      ],
      NOW,
    );
    expect(rows.map((r) => r.name)).toEqual(["乙", "甲"]);
  });

  it("到期后店铺已停摆：会话已过期、代理已到期为 error（danger）", () => {
    expect(rowFor({ health: "expiring", expires_at: daysFromNow(-1) })).toMatchObject({
      label: "已过期",
      tone: "danger",
      severity: "error",
    });
    expect(rowFor({ proxy_expires_at: daysFromNow(-1) })).toMatchObject({
      label: "代理已到期",
      tone: "danger",
      severity: "error",
    });
    expect(summarizeHealth([makeShop({ proxy_expires_at: daysFromNow(-1) })], NOW)).toMatchObject({
      level: "error",
      errorCount: 1,
    });
  });

  it("到期状态排在出口 IP 已变化之后、会话即将过期之前", () => {
    expect(rowFor({ egress_status: "changed", egress_ip_pending: "1.2.3.5", proxy_expires_at: daysFromNow(-1) }).label).toBe(
      "出口 IP 已变为 1.2.3.5，需确认",
    );
    expect(rowFor({ health: "expiring", expires_at: daysFromNow(-1), proxy_expires_at: daysFromNow(-1) }).label).toBe("已过期");
    expect(rowFor({ health: "expiring", expires_at: daysFromNow(2), proxy_expires_at: daysFromNow(-1) }).label).toBe(
      "代理已到期",
    );
  });
});

import { groupForPanel, levelTone, shouldAlert, type NotificationItem } from "./notification-view";

const item = (over: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 1, kind: "new_order", level: "medium", shop_id: 1, state_key: null, title: "示例店 新增 1 单",
  body: null, link: "/orders", count: 1, read_at: null, resolved_at: null,
  created_at: "2026-11-25T08:00:00", updated_at: "2026-11-25T08:00:00", ...over,
});

describe("levelTone", () => {
  it("强 → danger，中 → warning，弱 → info", () => {
    expect(levelTone("strong")).toBe("danger");
    expect(levelTone("medium")).toBe("warning");
    expect(levelTone("weak")).toBe("info");
  });
});

describe("groupForPanel", () => {
  it("未解决的状态类在 open，其余按原顺序在 recent", () => {
    const items = [
      item({ id: 1 }),
      item({ id: 2, kind: "login_expired", level: "strong", state_key: "login:1" }),
      item({ id: 3, kind: "egress_unreachable", level: "strong", state_key: "egress:1", resolved_at: "2026-11-25T09:00:00" }),
      item({ id: 4, kind: "risk_paused", level: "strong", state_key: "risk:2" }),
    ];
    const { open, recent } = groupForPanel(items);
    expect(open.map((i) => i.id)).toEqual([2, 4]);
    expect(recent.map((i) => i.id)).toEqual([1, 3]);
  });
});

describe("shouldAlert", () => {
  it("只对 alert=true 且未处理过的 id 返回 true", () => {
    expect(shouldAlert({ action: "created", item: item({ id: 5 }), alert: true }, [])).toBe(true);
    expect(shouldAlert({ action: "created", item: item({ id: 5 }), alert: true }, [5])).toBe(false);
    expect(shouldAlert({ action: "updated", item: item({ id: 6 }), alert: false }, [])).toBe(false);
    expect(shouldAlert({ action: "read", item: null, alert: false }, [])).toBe(false);
  });
});

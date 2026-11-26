import { alertNotice, bannerView, openRows, groupForPanel, lastPage, levelTone, shouldAlert, type NotificationItem, type StrongOpenShop } from "./notification-view";

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
  it("只对 alert=true 且未处理过的 id + 数量返回 true", () => {
    expect(shouldAlert({ action: "created", item: item({ id: 5 }), alert: true }, [])).toBe(true);
    expect(shouldAlert({ action: "created", item: item({ id: 5 }), alert: true }, ["5:1"])).toBe(false);
    // 未读时又来新单：同一条合并后数量变多，再提醒
    expect(shouldAlert({ action: "updated", item: item({ id: 5, count: 2 }), alert: true }, ["5:1"])).toBe(true);
    expect(shouldAlert({ action: "updated", item: item({ id: 6 }), alert: false }, [])).toBe(false);
    expect(shouldAlert({ action: "read", item: null, alert: false }, [])).toBe(false);
  });
});

describe("bannerView", () => {
  const shop = (id: number, problems: StrongOpenShop["problems"]): StrongOpenShop => ({
    shop_id: id, shop_name: `店${id}`, kinds: problems.map((p) => p.kind), link: problems[0]?.link ?? null, problems,
  });

  it("一店一行，同店问题用顿号连起来，每个问题跳各自的链接", () => {
    const view = bannerView([
      shop(1, [{ kind: "login_expired", link: "/shops?shop=1" }, { kind: "ship_deadline", link: "/orders?quick=ship_delay&shops=1" }]),
      shop(2, [{ kind: "ship_deadline", link: "/orders?quick=exp_ship&shops=2" }]),
    ]);
    expect(view).toEqual({
      kind: "rows",
      rows: [
        {
          shopId: 1, shopName: "店1", text: "店1：登录失效、临近发货超时",
          problems: [
            { kind: "login_expired", label: "登录失效", link: "/shops?shop=1" },
            { kind: "ship_deadline", label: "临近发货超时", link: "/orders?quick=ship_delay&shops=1" },
          ],
        },
        {
          shopId: 2, shopName: "店2", text: "店2：临近发货超时",
          problems: [{ kind: "ship_deadline", label: "临近发货超时", link: "/orders?quick=exp_ship&shops=2" }],
        },
      ],
    });
  });

  it("没有链接时登录 / 出口 / 风控回到店铺页高亮该店，临近超时去该店订单（不筛掉已超时）", () => {
    const view = bannerView([shop(3, [{ kind: "risk_paused", link: null }]), shop(4, [{ kind: "ship_deadline", link: null }])]);
    expect(view.kind === "rows" && view.rows.map((r) => r.problems[0].link)).toEqual(["/shops?shop=3", "/orders?shops=4"]);
  });

  it("飞鸽等待超时显示「超 3 分钟未回复」，跳后端给的链接", () => {
    const view = bannerView([shop(1, [{ kind: "im_waiting", link: "/messages?shops=1&quick=overdue" }])]);
    expect(view.kind === "rows" && view.rows[0].text).toBe("店1：超 3 分钟未回复");
    expect(view.kind === "rows" && view.rows[0].problems[0].link).toBe("/messages?shops=1&quick=overdue");
  });

  it("超过 3 家合并为一行", () => {
    expect(bannerView([1, 2, 3, 4].map((id) => shop(id, [{ kind: "login_expired", link: null }])))).toEqual({ kind: "merged", text: "4 家店需要处理" });
  });

  it("没有问题时为空", () => {
    expect(bannerView([])).toEqual({ kind: "none" });
  });
});

describe("lastPage", () => {
  it("按总数与每页条数算最后一页，至少为 1", () => {
    expect(lastPage(41, 20)).toBe(3);
    expect(lastPage(40, 20)).toBe(2);
    expect(lastPage(0, 20)).toBe(1);
    expect(lastPage(5, 0)).toBe(1);
  });
});

describe("alertNotice", () => {
  it("事件类强档常驻、中档 5 秒、弱档不弹；有正文时接在标题后面", () => {
    expect(alertNotice(item({ id: 5, level: "strong", kind: "new_aftersale", title: "示例店 新增 1 个售后" }))).toEqual({
      text: "示例店 新增 1 个售后", tone: "danger", key: "notification:5", persistent: true,
    });
    expect(alertNotice(item({ id: 6, level: "medium", title: "示例店 订单同步失败", body: "出口不通" }))).toEqual({
      text: "示例店 订单同步失败，出口不通", tone: "warning", key: "notification:6", persistent: false, holdMs: 5000,
    });
    expect(alertNotice(item({ level: "weak" }))).toBeNull();
  });

  it("状态类（有 state_key）不弹：由顶部横条常驻显示", () => {
    expect(alertNotice(item({ level: "strong", kind: "login_expired", state_key: "login:1" }))).toBeNull();
    expect(alertNotice(item({ level: "strong", kind: "ship_deadline", state_key: "deadline:1" }))).toBeNull();
  });
});

describe("openRows", () => {
  it("待处理列出全部未解决的店，不合并", () => {
    const shops = [1, 2, 3, 4].map((id): StrongOpenShop => ({
      shop_id: id, shop_name: `店${id}`, kinds: ["login_expired"], link: null, problems: [{ kind: "login_expired", link: null }],
    }));
    expect(openRows(shops).map((r) => r.text)).toEqual(["店1：登录失效", "店2：登录失效", "店3：登录失效", "店4：登录失效"]);
  });
});

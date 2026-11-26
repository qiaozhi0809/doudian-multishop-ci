import {
  canRestart,
  clampPage,
  formatWait,
  isOverdue,
  ordersLink,
  selectionParam,
  senderLabel,
  waitSecondsAt,
} from "./message-page";

describe("formatWait", () => {
  it.each([
    [null, ""],
    [0, "0 秒"],
    [45, "45 秒"],
    [59, "59 秒"],
    [60, "1 分 0 秒"],
    [190, "3 分 10 秒"],
    [3599, "59 分 59 秒"],
    [3600, "1 小时 0 分"],
    [3900, "1 小时 5 分"],
    [90_000, "25 小时 0 分"],
  ])("%s 秒显示为「%s」", (seconds, text) => {
    expect(formatWait(seconds)).toBe(text);
  });
});

describe("isOverdue", () => {
  it("180 秒不算超时，181 秒算", () => {
    expect(isOverdue(180)).toBe(false);
    expect(isOverdue(181)).toBe(true);
  });

  it("没在等不算超时", () => {
    expect(isOverdue(null)).toBe(false);
  });
});

describe("waitSecondsAt", () => {
  const now = new Date("2026-11-26T08:00:00.900Z");

  it("从 waiting_since 起算，向下取整", () => {
    expect(waitSecondsAt("2026-11-26T07:56:50Z", now)).toBe(190);
  });

  it("没在等或时间无效为 null", () => {
    expect(waitSecondsAt(null, now)).toBeNull();
    expect(waitSecondsAt("不是时间", now)).toBeNull();
  });

  it("平台时钟略快于本机时记 0", () => {
    expect(waitSecondsAt("2026-11-26T08:00:05Z", now)).toBe(0);
  });
});

describe("senderLabel", () => {
  it.each([
    ["buyer", "买家"],
    ["agent", "客服"],
    ["robot", "智能客服"],
    ["platform", "平台"],
  ] as const)("%s → %s", (role, label) => {
    expect(senderLabel(role)).toBe(label);
  });
});

describe("ordersLink", () => {
  it("订单接口没有买家筛选，只带店铺", () => {
    expect(ordersLink(3)).toBe("/orders?shops=3");
  });
});

describe("selectionParam", () => {
  it("读写往返：conv=<shop_id>:<conversation_id>，会话编号里可以有冒号", () => {
    const selection = { shopId: 3, conversationId: "conv:test-1" };
    const params = selectionParam.write(new URLSearchParams("quick=overdue&page=2"), selection);
    expect(params.get("conv")).toBe("3:conv:test-1");
    expect(params.get("quick")).toBe("overdue");
    expect(params.get("page")).toBe("2");
    expect(selectionParam.read(params)).toEqual(selection);
  });

  it("写 null 清除选中", () => {
    expect(selectionParam.write(new URLSearchParams("conv=3:conv-test-1"), null).has("conv")).toBe(false);
  });

  it.each(["", "3", "3:", ":conv-test-1", "0:conv-test-1", "a:conv-test-1", "3:带中文", "3:a/b", `3:${"a".repeat(129)}`])(
    "不合法的值「%s」视为未选中",
    (raw) => {
      expect(selectionParam.read(new URLSearchParams({ conv: raw }))).toBeNull();
    },
  );

  it.each([".", ".."])("会话编号为「%s」会改变请求路径，视为未选中", (id) => {
    expect(selectionParam.read(new URLSearchParams({ conv: `3:${id}` }))).toBeNull();
  });
});

describe("canRestart", () => {
  it("只有需重新连接、稍后重试、已停止可以重新连接", () => {
    const states = ["off", "queued", "starting", "running", "backoff", "needs_refresh", "stopped"] as const;
    expect(states.filter(canRestart)).toEqual(["backoff", "needs_refresh", "stopped"]);
  });
});

describe("clampPage", () => {
  it("超出末页时回到末页", () => {
    expect(clampPage(3, 60, 50)).toBe(2);
    expect(clampPage(2, 0, 50)).toBe(1);
  });

  it("在范围内保持不变", () => {
    expect(clampPage(2, 60, 50)).toBe(2);
    expect(clampPage(1, 0, 50)).toBe(1);
  });
});

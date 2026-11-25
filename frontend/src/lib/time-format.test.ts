import { daysUntil, formatBjTime, formatRemaining, parseExpiry } from "./time-format";

describe("formatBjTime", () => {
  const originalTz = process.env.TZ;
  afterEach(() => {
    if (originalTz === undefined) delete process.env.TZ;
    else process.env.TZ = originalTz;
  });

  it.each(["America/New_York", "Asia/Tokyo", "UTC", "Pacific/Auckland"])(
    "format_bj_time_any_tz: 在 %s 下仍为北京时间",
    (tz) => {
      process.env.TZ = tz;
      expect(formatBjTime("2026-11-24T16:30:00Z")).toBe("2026-11-25 00:30");
    },
  );

  it("按北京时间跨天与补零", () => {
    expect(formatBjTime("2026-12-31T16:05:00Z")).toBe("2027-01-01 00:05");
    expect(formatBjTime("2026-11-25T00:00:00Z")).toBe("2026-11-25 08:00");
  });

  it("带偏移量的时间按真实时刻换算", () => {
    expect(formatBjTime("2026-11-25T00:30:00+08:00")).toBe("2026-11-25 00:30");
  });

  it("无时区标记的 ISO 串按 UTC 处理", () => {
    expect(formatBjTime("2026-11-24T16:30:00")).toBe("2026-11-25 00:30");
  });

  it("空值与无效值显示「暂无」", () => {
    expect(formatBjTime(null)).toBe("暂无");
    expect(formatBjTime("not-a-date")).toBe("暂无");
  });
});

describe("到期时间", () => {
  const NOW = new Date("2026-11-25T00:00:00Z");
  const at = (ms: number) => new Date(NOW.getTime() + ms).toISOString();
  const HOUR = 3_600_000;
  const DAY = 24 * HOUR;

  it("parseExpiry: 只有日期时，当天整天有效（北京时间当天结束）", () => {
    expect(parseExpiry("2026-11-28").toISOString()).toBe("2026-11-28T16:00:00.000Z");
    expect(parseExpiry("2026-11-28T00:00:00Z").toISOString()).toBe("2026-11-28T00:00:00.000Z");
  });

  it("daysUntil: 向上取整，过期为 0 或负数", () => {
    expect(daysUntil(at(3 * DAY), NOW)).toBe(3);
    expect(daysUntil(at(3 * DAY + HOUR), NOW)).toBe(4);
    expect(daysUntil(at(-DAY), NOW)).toBeLessThanOrEqual(0);
  });

  it("formatRemaining: 剩 N 天 / 剩 N 小时 / 已过期 / 暂无", () => {
    expect(formatRemaining(at(3 * DAY), NOW)).toBe("剩 3 天");
    expect(formatRemaining(at(5 * HOUR), NOW)).toBe("剩 5 小时");
    expect(formatRemaining(at(10 * 60_000), NOW)).toBe("剩 1 小时");
    expect(formatRemaining(at(-1), NOW)).toBe("已过期");
    expect(formatRemaining(null, NOW)).toBe("暂无");
    expect(formatRemaining("bad", NOW)).toBe("暂无");
  });
});

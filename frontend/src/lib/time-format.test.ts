import { formatBjTime } from "./time-format";

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

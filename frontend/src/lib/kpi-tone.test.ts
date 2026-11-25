import { isQuiet } from "./kpi-tone";

describe("指标卡含义色", () => {
  it("黄、红两类数为 0 时变灰，有数才亮；其他颜色一直亮", () => {
    expect(isQuiet("danger", 0)).toBe(true);
    expect(isQuiet("warning", null)).toBe(true);
    expect(isQuiet("danger", 3)).toBe(false);
    expect(isQuiet("info", 0)).toBe(false);
    expect(isQuiet("violet", 0)).toBe(false);
  });
});

import { EMPTY_TEXT, orEmpty } from "./empty-text";

describe("orEmpty", () => {
  it("空值显示暂无，有值原样返回", () => {
    expect(EMPTY_TEXT).toBe("暂无");
    expect(orEmpty(null)).toBe("暂无");
    expect(orEmpty(undefined)).toBe("暂无");
    expect(orEmpty("")).toBe("暂无");
    expect(orEmpty("示例")).toBe("示例");
  });
});

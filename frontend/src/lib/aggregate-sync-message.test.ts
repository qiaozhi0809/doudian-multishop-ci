import { summarizeSync } from "./aggregate-sync-message";

const okText = (n: number) => `${n} 家店同步完成`;

describe("summarizeSync", () => {
  it("没有店铺时提示先登录 / 解除暂停", () => {
    expect(summarizeSync([], okText)).toEqual({
      tone: "info",
      text: "没有可同步的店铺（需先登录或解除暂停）",
    });
  });

  it("全部成功", () => {
    expect(summarizeSync([{ shop_id: 1 }, { shop_id: 2 }], okText)).toEqual({
      tone: "success",
      text: "2 家店同步完成",
    });
  });

  it("部分失败：说明成功数与首个失败原因", () => {
    const msg = summarizeSync([{ shop_id: 1 }, { shop_id: 2, error: "会话失效" }], okText);
    expect(msg.tone).toBe("warning");
    expect(msg.text).toContain("1 家店同步成功");
    expect(msg.text).toContain("会话失效");
  });

  it("全部失败", () => {
    expect(summarizeSync([{ shop_id: 1, error: "店铺已暂停" }], okText)).toEqual({
      tone: "danger",
      text: "同步失败：店铺已暂停",
    });
  });
});

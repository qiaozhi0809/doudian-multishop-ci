import { syncMessage } from "./sync-message";

describe("syncMessage", () => {
  it("只有新开始的：已开始同步 N 家店", () => {
    expect(syncMessage({ started: [1, 2], already_running: [] })).toEqual({ tone: "success", text: "已开始同步 2 家店" });
  });
  it("只有正在同步的：N 家店正在同步中", () => {
    expect(syncMessage({ started: [], already_running: [3] })).toEqual({ tone: "info", text: "1 家店正在同步中" });
  });
  it("两种并存时一起说明", () => {
    expect(syncMessage({ started: [1], already_running: [2, 3] })).toEqual({
      tone: "success",
      text: "已开始同步 1 家店，2 家店正在同步中",
    });
  });
  it("都没有：说明没有可同步的店铺", () => {
    expect(syncMessage({ started: [], already_running: [] })).toEqual({ tone: "info", text: "没有可同步的店铺" });
  });
});

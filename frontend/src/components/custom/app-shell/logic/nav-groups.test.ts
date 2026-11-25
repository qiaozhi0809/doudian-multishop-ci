import { parseCollapsedGroups, serializeCollapsedGroups, toggleCollapsedGroup } from "./nav-groups";

describe("分组折叠状态", () => {
  it("没有存储或坏数据时全部展开", () => {
    expect(parseCollapsedGroups(null)).toEqual([]);
    expect(parseCollapsedGroups("not json")).toEqual([]);
    expect(parseCollapsedGroups("{\"a\":1}")).toEqual([]);
  });

  it("只保留已知分组 id，去重", () => {
    expect(parseCollapsedGroups('["orders","orders","bogus","finance"]')).toEqual(["orders", "finance"]);
    expect(parseCollapsedGroups('["orders",1,null]')).toEqual(["orders"]);
  });

  it("序列化时过滤未知 id", () => {
    expect(serializeCollapsedGroups(["orders", "bogus"])).toBe('["orders"]');
  });

  it("toggle 在折叠与展开之间切换，未知 id 不变", () => {
    expect(toggleCollapsedGroup([], "orders")).toEqual(["orders"]);
    expect(toggleCollapsedGroup(["orders", "finance"], "orders")).toEqual(["finance"]);
    expect(toggleCollapsedGroup(["orders"], "bogus")).toEqual(["orders"]);
  });
});

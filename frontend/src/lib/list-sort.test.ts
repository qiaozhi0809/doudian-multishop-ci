import { readSort, seqOffset, sortQuery, sortRows, writeSort } from "./list-sort";

describe("list-sort", () => {
  it("从 URL 读排序：白名单外的字段视为没有排序，order 缺省为升序", () => {
    expect(readSort(new URLSearchParams("sort=pay_time&order=desc"), ["pay_time"])).toEqual({ key: "pay_time", direction: "desc" });
    expect(readSort(new URLSearchParams("sort=pay_time"), ["pay_time"])).toEqual({ key: "pay_time", direction: "asc" });
    expect(readSort(new URLSearchParams("sort=raw_json&order=desc"), ["pay_time"])).toBeNull();
    expect(readSort(new URLSearchParams(""), ["pay_time"])).toBeNull();
  });

  it("写排序回到第 1 页，保留其他筛选", () => {
    const next = writeSort(new URLSearchParams("status=printed&page=3"), { key: "amount_cents", direction: "desc" });
    expect(next.toString()).toBe("status=printed&sort=amount_cents&order=desc");
    expect(writeSort(next, null).toString()).toBe("status=printed");
  });

  it("查询参数：没有排序时不带", () => {
    expect(sortQuery(null)).toEqual({});
    expect(sortQuery({ key: "pay_time", direction: "asc" })).toEqual({ sort: "pay_time", order: "asc" });
  });

  it("序号翻页连续：每页 50 时第 2 页从 51 开始", () => {
    expect(seqOffset(1, 50)).toBe(0);
    expect(seqOffset(2, 50) + 1).toBe(51);
  });

  it("前端排序：数字按大小，空值升降都在最后", () => {
    const rows = [{ n: 3 }, { n: null }, { n: 10 }, { n: 1 }];
    const get = (row: { n: number | null }) => row.n;
    expect(sortRows(rows, { key: "n", direction: "asc" }, get).map((r) => r.n)).toEqual([1, 3, 10, null]);
    expect(sortRows(rows, { key: "n", direction: "desc" }, get).map((r) => r.n)).toEqual([10, 3, 1, null]);
    expect(sortRows(rows, null, get)).toEqual(rows);
  });
});

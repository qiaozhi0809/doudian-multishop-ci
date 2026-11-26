import { fitColumns } from "./table-columns";

describe("fitColumns", () => {
  it("像素列宽换成百分比，并返回列宽之和作为有数据时的最小表宽", () => {
    const { columns, minWidth } = fitColumns([
      { key: "a", label: "甲", width: 100 },
      { key: "b", label: "乙", width: 300 },
    ]);
    expect(minWidth).toBe(400);
    expect(columns.map((column) => column.width)).toEqual(["25%", "75%"]);
  });

  it("没写宽度的列保持原样，不计入总宽", () => {
    const { columns, minWidth } = fitColumns([
      { key: "a", label: "甲", width: 100 },
      { key: "b", label: "乙" },
    ]);
    expect(minWidth).toBe(100);
    expect(columns[1].width).toBeUndefined();
  });

  it("固定列（序号）保留像素宽，其余列按除去固定列后的宽度换成百分比", () => {
    const { columns, minWidth } = fitColumns(
      [
        { key: "seq", label: "序号", width: 56 },
        { key: "a", label: "甲", width: 100 },
        { key: "b", label: "乙", width: 300 },
      ],
      ["seq"],
    );
    expect(minWidth).toBe(456);
    expect(columns.map((column) => column.width)).toEqual([56, "25%", "75%"]);
  });
});

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DataColumn } from "@/components/arc/sortable-data-table/sortable-data-table";
import { DataTable } from "./data-table";

type Row = { id: number; shop: string; amount: number | null };
const rows: Row[] = [
  { id: 1, shop: "店B", amount: 300 },
  { id: 2, shop: "店A", amount: null },
  { id: 3, shop: "店C", amount: 100 },
];
const columns: DataColumn<Row>[] = [
  { key: "shop", label: "店铺", sortable: true, width: 100 },
  { key: "amount", label: "金额", sortable: true, numeric: true, width: 80 },
];

/** 每行的 [序号, 店铺]。 */
const body = () =>
  within(screen.getAllByRole("rowgroup")[1])
    .getAllByRole("row")
    .map((tr) => within(tr).getAllByRole("cell").slice(0, 2).map((td) => td.textContent));

describe("DataTable", () => {
  it("第一列是序号，按偏移连续编号（第 2 页从 51 开始）", () => {
    render(<DataTable rows={rows} columns={columns} rowKey={(r) => String(r.id)} caption="t" emptyMessage="空" seqOffset={50} />);
    expect(screen.getAllByRole("columnheader")[0]).toHaveTextContent("序号");
    expect(body()).toEqual([["51", "店B"], ["52", "店A"], ["53", "店C"]]);
  });

  it("默认排序不显示排序状态；前端排序后序号跟着显示顺序，空值在最后", async () => {
    render(<DataTable rows={rows} columns={columns} rowKey={(r) => String(r.id)} caption="t" emptyMessage="空" />);
    expect(document.querySelector("[data-sorted]")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /金额/ }));
    expect(body()).toEqual([["1", "店C"], ["2", "店B"], ["3", "店A"]]);
    await userEvent.click(screen.getByRole("button", { name: /金额/ }));
    expect(body()).toEqual([["1", "店B"], ["2", "店C"], ["3", "店A"]]);
    expect(screen.getByRole("columnheader", { name: /金额/ })).toHaveAttribute("aria-sort", "descending");
  });

  it("列给了 sortValue 时前端按它排（显示文案的顺序），不按原始值", async () => {
    type S = { id: number; code: string };
    const label: Record<string, string> = { b: "空闲", a: "已过期", c: "已用于" };
    const rank: Record<string, number> = { b: 0, c: 1, a: 2 };
    render(
      <DataTable<S>
        rows={[{ id: 1, code: "a" }, { id: 2, code: "b" }, { id: 3, code: "c" }]}
        columns={[{ key: "code", label: "状态", sortable: true, width: 100, sortValue: (r) => rank[r.code], render: (v) => label[String(v)] }]}
        rowKey={(r) => String(r.id)}
        caption="t"
        emptyMessage="空"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /状态/ }));
    expect(body().map(([, text]) => text)).toEqual(["空闲", "已用于", "已过期"]);
  });

  it("服务端排序：点表头只回调新排序，行顺序保持服务端给的", async () => {
    const onSortChange = vi.fn();
    const { rerender } = render(
      <DataTable rows={rows} columns={columns} rowKey={(r) => String(r.id)} caption="t" emptyMessage="空" sort={null} onSortChange={onSortChange} serverSorted />,
    );
    await userEvent.click(screen.getByRole("button", { name: /店铺/ }));
    expect(onSortChange).toHaveBeenCalledWith({ key: "shop", direction: "asc" });
    rerender(
      <DataTable rows={rows} columns={columns} rowKey={(r) => String(r.id)} caption="t" emptyMessage="空" sort={{ key: "shop", direction: "asc" }} onSortChange={onSortChange} serverSorted />,
    );
    expect(body().map((r) => r[1])).toEqual(["店B", "店A", "店C"]);
    expect(screen.getByRole("columnheader", { name: /店铺/ })).toHaveAttribute("aria-sort", "ascending");
    await userEvent.click(screen.getByRole("button", { name: /店铺/ }));
    expect(onSortChange).toHaveBeenLastCalledWith({ key: "shop", direction: "desc" });
  });

  it("没写 sortable: true 的列不能排序", () => {
    render(
      <DataTable rows={rows} columns={[{ key: "shop", label: "店铺", width: 100 }]} rowKey={(r) => String(r.id)} caption="t" emptyMessage="空" />,
    );
    expect(screen.queryByRole("button", { name: /店铺/ })).toBeNull();
  });
});

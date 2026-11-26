import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ListPager } from "./list-pager";

const base = { page: 1, pageSize: 50, onPageChange: vi.fn(), label: "订单分页", noun: "单" };

describe("ListPager", () => {
  it("没有数据时整条不显示", () => {
    const { container } = render(<ListPager {...base} total={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("只有一页时只显示合计，不显示翻页", () => {
    render(<ListPager {...base} total={12} />);
    expect(screen.getByText("共 12 单，每页 50 单")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "订单分页" })).not.toBeInTheDocument();
  });

  it("多页时显示翻页；每页量词可与合计不同", () => {
    render(<ListPager {...base} total={120} noun="个商品" pageUnit="个" label="商品分页" />);
    expect(screen.getByText("共 120 个商品，每页 50 个")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "商品分页" })).toBeInTheDocument();
  });
});

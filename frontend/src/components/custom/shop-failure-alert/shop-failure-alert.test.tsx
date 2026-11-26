import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { formatBjTime } from "@/lib/time-format";
import { CountMeta } from "./count-meta";
import { ShopFailureAlert } from "./shop-failure-alert";

const names: Record<number, string> = { 1: "店铺甲", 2: "店铺乙" };
const shopName = (id: number) => names[id] ?? `店铺 ${id}`;
const failures = [
  { shopId: 1, error: "平台接口报错" },
  { shopId: 2, error: null },
];

describe("ShopFailureAlert", () => {
  it("没有未取到的店时什么都不显示", () => {
    const { container } = render(<ShopFailureAlert failures={[]} shopName={shopName} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("显示 N 家店未取到，默认不列原因", () => {
    render(<ShopFailureAlert failures={failures} shopName={shopName} />);
    expect(screen.getByRole("status")).toHaveTextContent("2 家店未取到");
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看原因" })).toHaveAttribute("aria-expanded", "false");
  });

  it("展开看是哪几家及原因（没有原因时给兜底说法），可收起", async () => {
    render(<ShopFailureAlert failures={failures} shopName={shopName} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "店铺甲：平台接口报错",
      "店铺乙：原因未知，请稍后重试",
    ]);
    const collapse = screen.getByRole("button", { name: "收起原因" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    await user.click(collapse);
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });

  it("已在顶部横条的店不计数、不列出", async () => {
    render(<ShopFailureAlert failures={failures} shopName={shopName} bannerShopIds={new Set([2])} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 家店未取到");
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByRole("listitem")).toHaveTextContent("店铺甲：平台接口报错");
    expect(screen.queryByText(/店铺乙/)).not.toBeInTheDocument();
  });

  it("全部都在顶部横条时整条不显示", () => {
    const { container } = render(<ShopFailureAlert failures={failures} shopName={shopName} bannerShopIds={new Set([1, 2])} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("同一家店多个来源失败只算一家，保留第一条原因", async () => {
    render(
      <ShopFailureAlert
        failures={[{ shopId: 1, error: "订单计数失败" }, { shopId: 1, error: "商品计数失败" }]}
        shopName={shopName}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("1 家店未取到");
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByRole("listitem")).toHaveTextContent("店铺甲：订单计数失败");
  });
});

describe("CountMeta", () => {
  it("显示数据时间，悬停看完整时间", () => {
    const iso = "2026-11-20T01:30:00Z";
    render(<CountMeta fetchedAt={iso} />);
    expect(screen.getByText(/^数据时间 /)).toHaveAttribute("title", formatBjTime(iso));
    expect(screen.queryByText("合计不含未取到的店铺")).not.toBeInTheDocument();
  });

  it("有店没取到时写明合计不含这些店", () => {
    render(<CountMeta fetchedAt={null} partial />);
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
    expect(screen.queryByText(/数据时间/)).not.toBeInTheDocument();
  });

  it("两样都没有时整行不显示", () => {
    const { container } = render(<CountMeta fetchedAt={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

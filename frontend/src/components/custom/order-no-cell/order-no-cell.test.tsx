import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OrderNoCell } from "./order-no-cell";

/** userEvent.setup() 会装自己的剪贴板替身，之后再覆盖 */
function setupClipboard(writeText: (text: string) => Promise<void>) {
  const user = userEvent.setup();
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return user;
}

describe("OrderNoCell", () => {
  afterEach(() => {
    Reflect.deleteProperty(document, "execCommand");
  });

  it("点击复制单号，就地显示已复制", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = setupClipboard(writeText);
    render(<OrderNoCell value="6900000000000000001" />);
    const button = screen.getByRole("button", { name: "6900000000000000001" });
    expect(button).toHaveAttribute("title", "点击复制订单号");
    await user.click(button);
    expect(writeText).toHaveBeenCalledWith("6900000000000000001");
    expect(await screen.findByText("已复制")).toBeInTheDocument();
  });

  it("noun 换悬停提示（如售后单号）", () => {
    render(<OrderNoCell value="140000000000000001" noun="售后单号" />);
    expect(screen.getByRole("button", { name: "140000000000000001" })).toHaveAttribute("title", "点击复制售后单号");
  });

  it("复制失败时提示手动选择", async () => {
    const user = setupClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    Object.defineProperty(document, "execCommand", { value: () => false, configurable: true });
    render(<OrderNoCell value="690001" />);
    await user.click(screen.getByRole("button", { name: "690001" }));
    expect(await screen.findByText("复制失败，请手动选择")).toBeInTheDocument();
  });

  it.each([null, undefined, ""])("没有单号（%j）时显示暂无，不给按钮", (value) => {
    render(<OrderNoCell value={value} />);
    expect(screen.getByText("暂无")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

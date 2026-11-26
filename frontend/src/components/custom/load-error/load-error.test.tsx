import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoadError } from "./load-error";

describe("LoadError", () => {
  it("用报错提示条写明原因", () => {
    render(<LoadError title="读取订单失败，请确认本地服务正常后重试" onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("读取订单失败，请确认本地服务正常后重试");
  });

  it("点「重新读取」调用 onRetry", async () => {
    const onRetry = vi.fn();
    render(<LoadError title="读取失败" onRetry={onRetry} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("size 决定重试按钮尺寸：默认与 md 相同，sm 不同", () => {
    const classOf = (size?: "sm" | "md") => {
      const view = render(<LoadError title="读取失败" onRetry={() => {}} size={size} />);
      const className = view.getByRole("button", { name: "重新读取" }).className;
      view.unmount();
      return className;
    };
    expect(classOf()).toBe(classOf("md"));
    expect(classOf("sm")).not.toBe(classOf("md"));
  });

  it("className 加在外层容器上", () => {
    const { container } = render(<LoadError title="读取失败" onRetry={() => {}} className="inset" />);
    expect(container.firstElementChild).toHaveClass("inset");
  });
});

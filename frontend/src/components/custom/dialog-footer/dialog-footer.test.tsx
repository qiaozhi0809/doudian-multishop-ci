import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogContent } from "@/components/arc/dialog/dialog";
import { DialogFooter } from "./dialog-footer";

function renderFooter(busy = false) {
  const onOpenChange = vi.fn();
  render(
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent title="编辑代理">
        <DialogFooter busy={busy}>
          <Button>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>,
  );
  return onOpenChange;
}

describe("DialogFooter", () => {
  it("ghost「取消」在左、主按钮在右", () => {
    renderFooter();
    const cancel = screen.getByRole("button", { name: "取消" });
    expect(cancel.className).toMatch(/ghost/);
    const buttons = within(cancel.parentElement!).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["取消", "保存"]);
  });

  it("点「取消」关闭对话框", async () => {
    const onOpenChange = renderFooter();
    await userEvent.setup().click(screen.getByRole("button", { name: "取消" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("请求进行中「取消」置灰", () => {
    renderFooter(true);
    expect(screen.getByRole("button", { name: "取消" })).toBeDisabled();
  });
});

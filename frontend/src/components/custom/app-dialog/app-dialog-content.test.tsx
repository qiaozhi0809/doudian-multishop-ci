import { useEffect } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Dialog } from "@/components/arc/dialog/dialog";
import { NoticeProvider, useNotice } from "@/components/custom/notice/notice";
import { AppDialogContent, type DialogSize } from "./app-dialog-content";

function renderDialog(size: DialogSize) {
  render(
    <Dialog open>
      <AppDialogContent size={size} title="标题">
        <p>正文</p>
      </AppDialogContent>
    </Dialog>,
  );
  return screen.getByRole("dialog", { name: "标题" });
}

function PushNotice() {
  const notify = useNotice();
  useEffect(() => notify?.("示例店 新增 1 个售后", "danger", { persistent: true }), [notify]);
  return null;
}

describe("AppDialogContent", () => {
  it("确认框不带 ×", () => {
    renderDialog("confirm");
    expect(screen.queryByRole("button", { name: "关闭" })).not.toBeInTheDocument();
  });

  it.each(["form", "wide"] as const)("%s 档带 ×", (size) => {
    renderDialog(size);
    expect(screen.getByRole("button", { name: "关闭" })).toBeInTheDocument();
  });

  it("没有说明时不挂 aria-describedby", () => {
    expect(renderDialog("form")).not.toHaveAttribute("aria-describedby");
  });

  it("点右下角提示不关闭对话框，点别处才关", async () => {
    const onOpenChange = vi.fn();
    render(
      <MemoryRouter>
        <NoticeProvider>
          <PushNotice />
          <Dialog open onOpenChange={onOpenChange}>
            <AppDialogContent size="form" title="编辑代理">
              <p>正文</p>
            </AppDialogContent>
          </Dialog>
        </NoticeProvider>
      </MemoryRouter>,
    );
    // 模态对话框打开时页面其余部分不可点（jsdom 里 pointer-events 继承自 body），关掉这项检查
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await user.click(await screen.findByRole("button", { name: "关闭提示", hidden: true }));
    expect(onOpenChange).not.toHaveBeenCalled();
    await user.click(document.body);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

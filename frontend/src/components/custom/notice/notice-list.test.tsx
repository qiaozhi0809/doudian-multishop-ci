import { act, render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NoticeProvider } from "./notice";
import { NoticeList } from "./notice-list";
import { useNoticeQueue } from "./use-notice-queue";

describe("useNoticeQueue", () => {
  it("同 key 只留最新一条，可逐条关闭", () => {
    const { result } = renderHook(() => useNoticeQueue());
    act(() => result.current.notify("check:1", "danger", "第一次"));
    act(() => result.current.notify("check:1", "success", "第二次"));
    act(() => result.current.notify("check:2", "success", "另一条"));
    expect(result.current.notices.map((n) => n.text)).toEqual(["第二次", "另一条"]);
    act(() => result.current.dismissNotice(result.current.notices[0].id));
    expect(result.current.notices.map((n) => n.text)).toEqual(["另一条"]);
  });
});

describe("NoticeList", () => {
  const notices = [{ id: 1, key: "k", tone: "success" as const, text: "已保存" }];

  it("没有 Provider 时退回页面内提示条", () => {
    render(<NoticeList notices={notices} onDismiss={() => {}} />);
    expect(screen.getByText("已保存")).toBeInTheDocument();
    expect(screen.queryByLabelText("操作提示")).toBeNull();
  });

  it("有 Provider 时交给右下角浮动提示并清出队列", () => {
    const onDismiss = vi.fn();
    render(
      <MemoryRouter>
        <NoticeProvider>
          <NoticeList notices={notices} onDismiss={onDismiss} />
        </NoticeProvider>
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("操作提示")).toHaveTextContent("已保存");
    expect(onDismiss).toHaveBeenCalledWith(1);
  });
});

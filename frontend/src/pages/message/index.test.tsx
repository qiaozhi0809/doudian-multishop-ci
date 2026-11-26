import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeConversation, secondsAgo } from "@/test/im-fixtures";
import { LIST, calls, detail, lastList, list, listPage, mockIm, renderPage, row, setupImPageTests } from "@/test/im-page";
import { errorResponse } from "@/test/mock-fetch";

setupImPageTests();

describe("客服消息页：列表与计数", () => {
  it("渲染四张计数卡；点「超 3 分钟未回复」带 quick=overdue，再点清除", async () => {
    const fn = mockIm();
    renderPage();
    for (const name of ["未读会话 4", "待回复 3", "超 3 分钟未回复 1", "今日会话 9"]) {
      expect(await screen.findByRole("button", { name })).toBeInTheDocument();
    }
    expect(lastList(fn).get("quick")).toBeNull();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "超 3 分钟未回复 1" }));
    await waitFor(() => expect(lastList(fn).get("quick")).toBe("overdue"));
    await user.click(screen.getByRole("button", { name: "超 3 分钟未回复 1" }));
    await waitFor(() => expect(screen.getByTestId("where")).not.toHaveTextContent("quick"));
    expect(screen.getByRole("button", { name: "超 3 分钟未回复 1" })).toHaveAttribute("aria-pressed", "false");
  });

  it("勾「只看未读」请求带 unread=true，并回到第 1 页", async () => {
    const fn = mockIm({ [LIST]: () => listPage([makeConversation()], 60, 2) });
    renderPage("/messages?page=2");
    await list();
    expect(lastList(fn).has("unread")).toBe(false);
    await userEvent.setup().click(screen.getByRole("checkbox", { name: "只看未读" }));
    await waitFor(() => expect(lastList(fn).get("unread")).toBe("true"));
    expect(lastList(fn).get("page")).toBe("1");
    expect(screen.getByTestId("where")).toHaveTextContent("unread=1");
  });

  it("店铺筛选与排序原样发给接口", async () => {
    const fn = mockIm();
    renderPage("/messages?shops=1&sort=unread&order=desc");
    await list();
    expect(lastList(fn).get("shop_ids")).toBe("1");
    expect(lastList(fn).get("sort")).toBe("unread");
    expect(lastList(fn).get("order")).toBe("desc");
    expect(calls(fn, "/api/im/conversations/counts").at(-1)).toContain("shop_ids=1");
  });

  it("行内显示买家、店铺、预览、等待时间与未读数；超 3 分钟的行带 data-overdue", async () => {
    mockIm({
      [LIST]: () =>
        listPage([
          makeConversation({ waiting_since: secondsAgo(200) }),
          makeConversation({ conversation_id: "conv-test-2", buyer: "买家 · 尾号 st-2", preview: "好的", unread: 0, waiting_since: secondsAgo(70) }),
          makeConversation({ conversation_id: "conv-test-3", buyer: "测试买家丙", unread: 0, waiting_since: null, wait_seconds: null }),
        ]),
    });
    renderPage();
    await list();
    const first = await row(/测试买家 /);
    expect(first).toHaveAttribute("data-overdue");
    for (const text of ["测试买家", "测试小铺", "在吗", "2"]) expect(within(first).getByText(text)).toBeInTheDocument();
    expect(within(first).getByText(/^等待 3 分 \d+ 秒$/)).toBeInTheDocument();
    const second = await row(/尾号 st-2/);
    expect(second).not.toHaveAttribute("data-overdue");
    expect(within(second).getByText(/^等待 1 分 \d+ 秒$/)).toBeInTheDocument();
    expect(within(await row(/测试买家丙/)).queryByText(/^等待/)).not.toBeInTheDocument();
  });

  it("等待时间每秒走秒，过 3 分钟标红", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false, toFake: ["Date", "setInterval", "clearInterval"] });
    vi.setSystemTime(new Date("2026-11-26T08:00:00Z"));
    mockIm({ [LIST]: () => listPage([makeConversation({ waiting_since: "2026-11-26T07:57:00Z" })]) });
    renderPage();
    await list();
    const item = await row();
    expect(within(item).getByText("等待 3 分 0 秒")).toBeInTheDocument();
    expect(item).not.toHaveAttribute("data-overdue");
    act(() => void vi.advanceTimersByTime(1000));
    expect(within(item).getByText("等待 3 分 1 秒")).toBeInTheDocument();
    expect(item).toHaveAttribute("data-overdue");
  });

  it("每 30 秒重取一次列表", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"], shouldAdvanceTime: true });
    const fn = mockIm();
    renderPage();
    await list();
    const before = calls(fn, "/api/im/conversations").length;
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    await waitFor(() => expect(calls(fn, "/api/im/conversations").length).toBeGreaterThan(before));
  });

  it.each(["im_wait_changed", "im_unread_changed", "im_stopped"])("收到 %s 事件后重新请求列表与计数", async (event) => {
    const fn = mockIm();
    renderPage();
    await list();
    const before = calls(fn, "/api/im/conversations").length;
    const countsBefore = calls(fn, "/api/im/conversations/counts").length;
    act(() => FakeEventSource.latest().emit(event, { shop_id: 1 }));
    await waitFor(() => expect(calls(fn, "/api/im/conversations").length).toBeGreaterThan(before));
    expect(calls(fn, "/api/im/conversations/counts").length).toBeGreaterThan(countsBefore);
  });

  it("没有会话时显示「暂无会话」，右栏「选择一个会话」", async () => {
    mockIm({ [LIST]: () => listPage([]) });
    renderPage();
    expect(await screen.findByText("暂无会话")).toBeInTheDocument();
    expect(within(detail()).getByText("选择一个会话")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "在飞鸽中回复" })).not.toBeInTheDocument();
  });

  it("页码超出末页时回到末页", async () => {
    mockIm({ [LIST]: () => listPage([], 60, 3) });
    renderPage("/messages?page=3");
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("page=2"));
  });

  it("读取列表失败时给出重试", async () => {
    mockIm({ [LIST]: () => errorResponse(500, "InternalError") });
    renderPage();
    expect(await screen.findByText("读取会话失败，请确认本地服务正常后重试")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新读取" })).toBeInTheDocument();
  });
});

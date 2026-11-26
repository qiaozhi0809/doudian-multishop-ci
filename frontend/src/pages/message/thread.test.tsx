import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeConversation, makeImStatus } from "@/test/im-fixtures";
import { LIST, OPEN, STATUS, THREAD, detail, list, listPage, mockIm, openRow, renderPage, row, thread, setupImPageTests } from "@/test/im-page";
import { errorResponse, jsonResponse } from "@/test/mock-fetch";

setupImPageTests();

describe("客服消息页：会话详情", () => {
  it("点一行后右栏显示买家、店铺、等待时间与消息；平台消息是系统行", async () => {
    mockIm();
    renderPage();
    await openRow();
    expect(screen.getByTestId("where")).toHaveTextContent("conv=1%3Aconv-test-1");
    const pane = within(detail());
    expect(await pane.findByText("在的")).toBeInTheDocument();
    expect(pane.getByRole("heading", { name: "测试买家" })).toBeInTheDocument();
    expect(pane.getByText("测试小铺")).toBeInTheDocument();
    expect(pane.getByText(/^等待 3 分 \d+ 秒$/)).toBeInTheDocument();
    const messages = pane.getAllByRole("listitem");
    expect(messages.map((m) => m.dataset.role)).toEqual(["buyer", "platform", "agent"]);
    expect(within(messages[0]).getByText("买家")).toBeInTheDocument();
    expect(within(messages[1]).getByText("平台")).toBeInTheDocument();
    expect(within(messages[2]).getByText("客服")).toBeInTheDocument();
    expect(messages[0].querySelector("time")).toHaveAttribute("datetime");
    expect(await row()).toHaveAttribute("aria-current", "true");
  });

  it("「在飞鸽中回复」发 POST", async () => {
    const fn = mockIm();
    renderPage();
    await openRow();
    await userEvent.setup().click(within(detail()).getByRole("button", { name: "在飞鸽中回复" }));
    await waitFor(() =>
      expect(
        fn.mock.calls.filter(
          ([input, init]) => init?.method === "POST" && String(input) === "/api/im/conversations/1/conv-test-1/open-in-flybird",
        ),
      ).toHaveLength(1),
    );
    expect(screen.queryByText("飞鸽里没找到该会话")).not.toBeInTheDocument();
  });

  it("「查看订单」是按钮，跳到只带该店的订单页", async () => {
    mockIm();
    renderPage();
    await openRow();
    expect(within(detail()).queryByRole("link", { name: "查看订单" })).not.toBeInTheDocument();
    await userEvent.setup().click(within(detail()).getByRole("button", { name: "查看订单" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(/^\/orders\?shops=1$/));
  });

  it("飞鸽里没定位到会话时提示", async () => {
    mockIm({ [OPEN]: () => jsonResponse({ result: "not_found" }) });
    renderPage("/messages?conv=1:conv-test-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "在飞鸽中回复" }));
    expect(await screen.findByText("飞鸽里没找到该会话")).toBeInTheDocument();
  });

  it("该店没在接收时显示后端原因", async () => {
    mockIm({ [OPEN]: () => errorResponse(422, "InvalidRequest", "该店飞鸽未在接收") });
    renderPage("/messages?conv=1:conv-test-1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "在飞鸽中回复" }));
    expect(await screen.findByText("该店飞鸽未在接收")).toBeInTheDocument();
  });

  it("还没采集到消息时显示最新预览", async () => {
    mockIm({ [THREAD]: () => thread([]) });
    renderPage();
    await openRow();
    const pane = within(detail());
    expect(await pane.findByText("最新消息")).toBeInTheDocument();
    expect(pane.getByText("在吗")).toBeInTheDocument();
  });

  it("读取消息失败时给出原因与重试，两个按钮仍在", async () => {
    mockIm({ [THREAD]: () => errorResponse(404, "NotFound", "会话不存在") });
    renderPage();
    await openRow();
    const pane = within(detail());
    expect(await pane.findByText("读取消息失败：会话不存在")).toBeInTheDocument();
    expect(pane.getByRole("button", { name: "重新读取" })).toBeInTheDocument();
    expect(pane.getByRole("button", { name: "在飞鸽中回复" })).toBeInTheDocument();
  });

  it("会话从当前列表消失后保留买家与店铺，不再显示等待时间", async () => {
    let items = [makeConversation()];
    mockIm({ [LIST]: () => listPage(items) });
    renderPage("/messages?quick=overdue");
    await openRow();
    items = [];
    act(() => FakeEventSource.latest().emit("im_wait_changed", { shop_id: 1 }));
    await screen.findByText("暂无会话");
    const pane = within(detail());
    expect(pane.getByRole("heading", { name: "测试买家" })).toBeInTheDocument();
    expect(pane.queryByText(/^等待/)).not.toBeInTheDocument();
  });

  it("选中的店不在店铺筛选里时右栏清空", async () => {
    mockIm();
    renderPage("/messages?shops=2&conv=1:conv-test-1");
    await list();
    expect(within(detail()).getByText("选择一个会话")).toBeInTheDocument();
  });

  it("页面上没有任何文本输入框", async () => {
    mockIm({ [STATUS]: () => jsonResponse([makeImStatus({ state: "stopped", state_label: "已停止" })]) });
    const { container } = renderPage();
    await openRow();
    await within(detail()).findByText("在的");
    await screen.findByLabelText("测试小铺：已停止");
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(container.querySelectorAll("textarea, input, [contenteditable]")).toHaveLength(0);
  });
});

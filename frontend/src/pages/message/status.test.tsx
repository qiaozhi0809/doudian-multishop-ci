import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeImStatus } from "@/test/im-fixtures";
import { STATUS, calls, mockIm, renderPage, setupImPageTests } from "@/test/im-page";
import { errorResponse, jsonResponse } from "@/test/mock-fetch";

setupImPageTests();

describe("客服消息页：接收状态", () => {
  const statuses = () =>
    jsonResponse([
      makeImStatus(),
      makeImStatus({ shop_id: 2, shop_name: "测试小铺二", state: "needs_refresh", state_label: "需重新连接" }),
      makeImStatus({ shop_id: 3, shop_name: "测试小铺三", state: "starting", state_label: "启动中" }),
    ]);

  it("只列不在接收中的店；可重连的带「重新连接」", async () => {
    const fn = mockIm({
      [STATUS]: statuses,
      "POST /api/im/shops/2/restart": () => jsonResponse(makeImStatus({ shop_id: 2, state: "queued", state_label: "排队中" })),
    });
    renderPage();
    expect(await screen.findByLabelText("测试小铺二：需重新连接")).toBeInTheDocument();
    expect(screen.getByLabelText("测试小铺三：启动中")).toBeInTheDocument();
    expect(screen.queryByLabelText(/^测试小铺：/)).not.toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "重新连接" });
    expect(buttons).toHaveLength(1);
    const before = calls(fn, "/api/im/status").length;
    await userEvent.setup().click(buttons[0]);
    await waitFor(() => expect(calls(fn, "/api/im/shops/2/restart")).toHaveLength(1));
    await waitFor(() => expect(calls(fn, "/api/im/status").length).toBeGreaterThan(before));
  });

  it("状态条跟随店铺筛选", async () => {
    mockIm({ [STATUS]: statuses });
    renderPage("/messages?shops=3");
    expect(await screen.findByLabelText("测试小铺三：启动中")).toBeInTheDocument();
    expect(screen.queryByLabelText("测试小铺二：需重新连接")).not.toBeInTheDocument();
  });

  it("重新连接失败时显示后端原因", async () => {
    mockIm({
      [STATUS]: statuses,
      "POST /api/im/shops/2/restart": () => errorResponse(422, "InvalidRequest", "该店未开启接收飞鸽消息"),
    });
    renderPage();
    await userEvent.setup().click(await screen.findByRole("button", { name: "重新连接" }));
    expect(await screen.findByText("该店未开启接收飞鸽消息")).toBeInTheDocument();
  });
});

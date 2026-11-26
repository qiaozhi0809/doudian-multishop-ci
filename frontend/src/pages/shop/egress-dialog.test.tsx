import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { mockPageFetch, renderPage } from "./page-test-utils";

let restore: () => void;
beforeEach(() => {
  restore = FakeEventSource.install();
});
afterEach(() => restore());

describe("设置出口", () => {
  it("粘贴代理商一行并保存：提交 paste 字段", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ status: "needs_login", egress_status: "unchecked" })]),
      "PUT /api/shops/1/egress": jsonResponse(makeShop()),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "粘贴" }));
    await user.type(within(dialog).getByLabelText("代理商格式"), "1.2.3.4|8000|user|pass|2026-12-31");
    await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(String(put[1]?.body))).toEqual({ mode: "proxy", paste: "1.2.3.4|8000|user|pass|2026-12-31" });
  });

  it("粘贴格式不对时提示，不发请求", async () => {
    const fetchMock = mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "粘贴" }));
    await user.type(within(dialog).getByLabelText("代理商格式"), "1.2.3.4|8000");
    await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
    expect(await within(dialog).findByText("代理商格式应为 IP|端口|账号|密码|到期日")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);
  });

  async function saveDirectEgress() {
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog", { name: "设置出口" });
    expect(within(dialog).getByText("该店已登录，修改出口后需要重新扫码")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "直连" }));
    await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
    const confirm = await screen.findByRole("dialog", { name: "修改出口 店铺甲" });
    return { user, dialog, confirm };
  }
  const putCalls = (fetchMock: ReturnType<typeof mockFetch>) => fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT");

  it("已登录的店铺：保存出口先确认（危险按钮），确认后才提交，两个弹窗都关闭", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "PUT /api/shops/1/egress": jsonResponse(makeShop()),
    });
    const { user, confirm } = await saveDirectEgress();
    expect(confirm).toHaveAccessibleDescription("保存后需要重新扫码登录");
    expect(putCalls(fetchMock)).toHaveLength(0);
    const button = within(confirm).getByRole("button", { name: "保存出口" });
    expect(button.className).toMatch(/danger/);
    await user.click(button);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(putCalls(fetchMock)).toHaveLength(1);
    expect(JSON.parse(String(putCalls(fetchMock)[0][1]?.body))).toEqual({ mode: "direct" });
  });

  it("已登录的店铺：确认框点取消，不提交，出口弹窗保留已填内容", async () => {
    const fetchMock = mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    const { user, dialog, confirm } = await saveDirectEgress();
    await user.click(within(confirm).getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "修改出口 店铺甲" })).not.toBeInTheDocument());
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "直连" })).toHaveAttribute("aria-pressed", "true");
    expect(putCalls(fetchMock)).toHaveLength(0);
  });

  it("已登录的店铺：后端拒绝时原因显示在确认框里", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "PUT /api/shops/1/egress": errorResponse(422, "InvalidRequest", "端口必须是数字"),
    });
    const { user, confirm } = await saveDirectEgress();
    await user.click(within(confirm).getByRole("button", { name: "保存出口" }));
    expect(await within(confirm).findByText("端口必须是数字")).toBeInTheDocument();
  });

  it("未登录的店铺：保存出口直接提交，后端拒绝时就地显示原因", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ status: "needs_login", egress_status: "unchecked" })]),
      "PUT /api/shops/1/egress": errorResponse(422, "InvalidRequest", "端口必须是数字"),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "直连" }));
    await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
    expect(await within(dialog).findByText("端口必须是数字")).toBeInTheDocument();
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
  });

  it("手填代理：可选字段用「可选」标记，不写「选填」", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "手填" }));
    expect(within(dialog).queryByText(/选填/)).not.toBeInTheDocument();
    expect(within(dialog).getAllByText("可选")).toHaveLength(2);
  });

  it("直连被别的店占用：禁用原因用提示气泡说明，不用 title", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop(), makeShop({ id: 2, name: "直连店", egress_mode: "direct" })]),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    const direct = within(dialog).getByRole("button", { name: "直连" });
    expect(direct).toBeDisabled();
    expect(within(dialog).queryByTitle(/使用直连/)).not.toBeInTheDocument();
    act(() => direct.closest<HTMLElement>("span[tabindex='0']")!.focus());
    expect(await screen.findByRole("tooltip")).toHaveTextContent("已有店铺「直连店」使用直连，最多一家店可直连");
  });

  it("出口 IP 变化时可以接受新 IP", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ egress_status: "changed", egress_ip_pending: "1.2.3.5" })]),
      "POST /api/shops/1/egress/check": jsonResponse({ egress_ip: "1.2.3.5", egress_ip_pending: null, egress_status: "ok" }),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    await user.click(await screen.findByRole("button", { name: "接受新 IP" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/shops/1/egress/check?accept_change=true"),
    );
    // 接受新 IP 不得顺带提交出口表单
    expect(screen.queryByText("请选择池里的代理")).toBeNull();
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "PUT")).toBe(false);
  });
});

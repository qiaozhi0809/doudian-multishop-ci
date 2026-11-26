import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

/** 店铺页测试统一带上备份快照的空响应，避免每个用例重复登记。 */
function mockPageFetch(routes: Parameters<typeof mockFetch>[0]) {
  return mockFetch({
    "GET /api/backup/snapshots": jsonResponse({ items: [], backups_dir: "", keep: 7 }),
    ...routes,
  });
}

function renderPage(path = "/shops") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ShopPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const rowOf = (name: string) => screen.getByRole("row", { name: new RegExp(name) });

let restore: () => void;
beforeEach(() => {
  restore = FakeEventSource.install();
});
afterEach(() => restore());

describe("店铺与设置页", () => {
  it("?shop=2 高亮第 2 店并滚动到该行；与全局筛选 shops= 互不影响", async () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" }), makeShop({ id: 3, name: "店铺丙" })]),
    });
    renderPage("/shops?shops=1,2&shop=2");
    await screen.findByRole("table");
    expect(screen.queryByRole("row", { name: /店铺丙/ })).not.toBeInTheDocument();
    expect(rowOf("店铺乙")).toHaveAttribute("aria-current", "true");
    expect(rowOf("店铺甲")).not.toHaveAttribute("aria-current");
    await waitFor(() => expect(scroll).toHaveBeenCalled());
    expect(scroll.mock.contexts[0]).toBe(rowOf("店铺乙"));
    // 排序会重新挂载表格：仍高亮，但不再滚动
    await userEvent.setup().click(within(screen.getByRole("columnheader", { name: "店铺" })).getByRole("button"));
    expect(rowOf("店铺乙")).toHaveAttribute("aria-current", "true");
    expect(scroll).toHaveBeenCalledTimes(1);
    scroll.mockRestore();
  });


  it("还没有店铺：显示引导添加店铺的空状态，而不是空表格", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "添加店铺" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("读取失败：区块内显示原因与重试按钮", async () => {
    let fail = true;
    mockPageFetch({ "GET /api/shops": () => (fail ? errorResponse(500, "Internal", "boom") : jsonResponse([makeShop()])) });
    renderPage();
    expect(await screen.findByText("读取店铺失败，请确认本地服务已启动后重试")).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("表格按规范显示会话、出口、取号就绪状态", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([
        makeShop({ id: 1, name: "店铺甲" }),
        makeShop({ id: 2, name: "店铺乙", status: "needs_login", health: "expired", egress_status: "duplicate", ready_for_label: false, not_ready_reasons: ["缺少默认发货地址"] }),
      ]),
    });
    renderPage();
    const a = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(a.getByText("正常")).toBeInTheDocument();
    expect(a.getByText("出口正常 · 1.2.3.4")).toBeInTheDocument();
    expect(a.getByText("就绪")).toBeInTheDocument();
    const b = within(rowOf("店铺乙"));
    expect(b.getByText("需重新登录")).toBeInTheDocument();
    expect(b.getByText("出口 IP 与其他店重复")).toBeInTheDocument();
    expect(b.getByText("未就绪")).toBeInTheDocument();
  });

  it("首列是序号；店铺名、平台店铺名、状态、到期可排序，出口、操作等列没有排序按钮", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    await screen.findByRole("table");
    const sortable = (name: string) => within(screen.getByRole("columnheader", { name })).queryByRole("button");
    expect(screen.getAllByRole("columnheader")[0]).toHaveTextContent("序号");
    for (const name of ["店铺", "平台店铺名", "状态", "到期"]) expect(sortable(name)).not.toBeNull();
    for (const name of ["序号", "负责人", "出口", "取号就绪", "操作"]) expect(sortable(name)).toBeNull();
  });

  it("全局店铺筛选只显示选中的店铺", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })]) });
    renderPage("/shops?shops=2");
    await screen.findByRole("row", { name: /店铺乙/ });
    expect(screen.queryByRole("row", { name: /店铺甲/ })).not.toBeInTheDocument();
  });

  it("出口未检查：直接显示「检查出口」按钮，不显示扫码登录；检查通过后换成扫码登录", async () => {
    let checked = false;
    mockPageFetch({
      "GET /api/shops": () => jsonResponse([makeShop({ egress_status: checked ? "ok" : "unchecked" })]),
      "POST /api/shops/1/egress/check": () => {
        checked = true;
        return jsonResponse({ egress_ip: "1.2.3.4", egress_ip_pending: null, egress_status: "ok" });
      },
    });
    renderPage();
    const user = userEvent.setup();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(row.getByRole("button", { name: "检查出口" })).toBeEnabled();
    expect(row.queryByRole("button", { name: "扫码登录" })).not.toBeInTheDocument();
    await user.click(row.getByRole("button", { name: "检查出口" }));
    expect(await within(screen.getByRole("row", { name: /店铺甲/ })).findByRole("button", { name: "扫码登录" })).toBeEnabled();
    expect(within(screen.getByRole("row", { name: /店铺甲/ })).queryByRole("button", { name: "检查出口" })).not.toBeInTheDocument();
  });

  it("还没有设置出口：直接显示「设置出口」，不显示扫码登录", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop({ egress_mode: null, egress_status: "unchecked" })]) });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(row.getByRole("button", { name: "设置出口" })).toBeInTheDocument();
    expect(row.queryByRole("button", { name: "扫码登录" })).not.toBeInTheDocument();
  });

  it("风控暂停的店铺出口正常时，扫码登录保持可见但禁用", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop({ paused_reason: "risk_blocked:1" })]) });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(row.getByRole("button", { name: "扫码登录" })).toBeDisabled();
  });

  it("扫码登录：提示去扫码并进入等待态，收到事件后提示成功", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "POST /api/shops/1/login": jsonResponse({ status: "started" }, 202),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "扫码登录" }));
    expect(await screen.findByText("店铺甲：请在弹出的浏览器窗口中扫码")).toBeInTheDocument();
    expect(within(rowOf("店铺甲")).getByText("等待扫码")).toBeInTheDocument();
    FakeEventSource.latest().emit("shop_status_changed", { shop_id: 1, status: "active" });
    expect(await screen.findByText("店铺甲：扫码登录成功")).toBeInTheDocument();
  });

  it("扫码登录失败（409 预检）显示后端的中文原因", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "POST /api/shops/1/login": errorResponse(409, "TaskAlreadyRunning", "该店已有扫码登录在进行", 1),
    });
    renderPage();
    await userEvent.setup().click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "扫码登录" }));
    expect(await screen.findByText("店铺甲：该店已有扫码登录在进行")).toBeInTheDocument();
  });

  it("风控暂停：只显示风控暂停，恢复需要先确认", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ paused_reason: "risk_blocked:602502151" })]),
      "POST /api/shops/1/resume": jsonResponse(makeShop()),
    });
    renderPage();
    const user = userEvent.setup();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(row.getByText("风控暂停")).toBeInTheDocument();
    expect(screen.queryByText(/602502151/)).not.toBeInTheDocument();
    await user.click(row.getByRole("button", { name: "恢复" }));
    const dialog = await screen.findByRole("dialog");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "确认恢复" }));
    expect(await screen.findByText("店铺甲：已解除风控暂停")).toBeInTheDocument();
  });

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

    it("已登录的店铺修改出口前提示需要重新扫码；后端拒绝时就地显示原因", async () => {
      mockPageFetch({
        "GET /api/shops": jsonResponse([makeShop()]),
        "PUT /api/shops/1/egress": errorResponse(422, "InvalidRequest", "端口必须是数字"),
      });
      renderPage();
      const user = userEvent.setup();
      await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
      await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
      const dialog = await screen.findByRole("dialog");
      expect(within(dialog).getByText("该店已登录，修改出口后需要重新扫码")).toBeInTheDocument();
      await user.click(within(dialog).getByRole("button", { name: "直连" }));
      await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
      expect(await within(dialog).findByText("端口必须是数字")).toBeInTheDocument();
    });

    it("出口 IP 变化时提供确认新 IP", async () => {
      const fetchMock = mockPageFetch({
        "GET /api/shops": jsonResponse([makeShop({ egress_status: "changed", egress_ip_pending: "1.2.3.5" })]),
        "POST /api/shops/1/egress/check": jsonResponse({ egress_ip: "1.2.3.5", egress_ip_pending: null, egress_status: "ok" }),
      });
      renderPage();
      const user = userEvent.setup();
      await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
      await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
      await user.click(await screen.findByRole("button", { name: "确认新 IP" }));
      await waitFor(() =>
        expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/shops/1/egress/check?accept_change=true"),
      );
      // 确认新 IP 不得顺带提交出口表单
      expect(screen.queryByText("请选择池里的代理")).toBeNull();
      expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "PUT")).toBe(false);
    });
  });

  it("添加店铺：成功后接着打开设置出口", async () => {
    const created = makeShop({ id: 9, name: "新店", egress_mode: null, egress_status: "unchecked", status: "needs_login" });
    let added = false;
    mockPageFetch({
      "GET /api/shops": () => jsonResponse(added ? [created] : []),
      "POST /api/shops": () => {
        added = true;
        return jsonResponse(created, 201);
      },
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "添加店铺" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("请输入店铺名称");
    await user.type(within(dialog).getByLabelText("店铺名称"), "新店");
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    expect(await screen.findByRole("dialog", { name: "设置出口" })).toBeInTheDocument();
  });

  it("查看店铺资料：列出各项，空的显示暂无", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "GET /api/shops/1/base": jsonResponse({
        addresses: [{ address_id: "a1", is_default: true, name: "仓库", phone: "138****0000", region: "某省某市" }],
        couriers: [{ courier_code: "yuantong", name: "圆通" }],
        templates: [],
        accounts: [{ ebill_id: "e1", courier_code: "yuantong", net_code: "n1", net_name: "圆通网点", is_default: true, balance: null }],
      }),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "店铺资料" }));
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("仓库")).toBeInTheDocument();
    expect(within(drawer).getByText("圆通")).toBeInTheDocument();
    expect(within(drawer).getByText("默认 · 余额 暂无")).toBeInTheDocument();
    expect(within(drawer).getAllByText("暂无").length).toBeGreaterThan(0);
  });
});

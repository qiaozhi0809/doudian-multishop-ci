import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse } from "@/test/mock-fetch";
import { mockPageFetch, renderPage } from "./page-test-utils";

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

  it("风控暂停：行内主按钮换成恢复，和「更多操作」同在操作列，不显示扫码登录", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop({ paused_reason: "risk_blocked:1" })]) });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(row.getByRole("button", { name: "恢复" }).closest("td")).toBe(row.getByRole("button", { name: "更多操作" }).closest("td"));
    expect(row.getByText("风控暂停").closest("td")!.querySelector("button")).toBeNull();
    expect(row.queryByRole("button", { name: "扫码登录" })).not.toBeInTheDocument();
  });

  it("风控暂停的原因在状态徽标上悬停查看", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop({ paused_reason: "risk_blocked:1" })]) });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    act(() => row.getByText("风控暂停").closest<HTMLElement>("[tabindex='0']")!.focus());
    expect(await screen.findByRole("tooltip")).toHaveTextContent("原因：risk_blocked:1");
  });

  it("状态类徽标都带圆点：会话、取号就绪、等待扫码", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "POST /api/shops/1/login": jsonResponse({ status: "started" }, 202),
    });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    await userEvent.setup().click(row.getByRole("button", { name: "扫码登录" }));
    await within(rowOf("店铺甲")).findByText("等待扫码");
    for (const label of ["正常", "就绪", "等待扫码"]) {
      const badge = within(rowOf("店铺甲")).getByText(label).closest("[class*='badge']")!;
      expect(badge.querySelector("[class*='dot']"), label).not.toBeNull();
    }
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
    const confirm = within(dialog).getByRole("button", { name: "恢复店铺" });
    expect(confirm.className).toMatch(/primary/);
    await user.click(confirm);
    expect(await screen.findByText("店铺甲：已解除风控暂停")).toBeInTheDocument();
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
    await user.click(await screen.findByRole("menuitem", { name: "查看店铺资料" }));
    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("仓库")).toBeInTheDocument();
    expect(within(drawer).getByText("圆通")).toBeInTheDocument();
    expect(within(drawer).getByText("默认 · 余额 暂无")).toBeInTheDocument();
    expect(within(drawer).getAllByText("暂无").length).toBeGreaterThan(0);
  });

  describe("数据备份", () => {
    const created = { file_name: "app-20261126-120000.db", size_bytes: 2048, trigger: "manual", actor: "admin", created_at: "2026-11-26T04:00:00Z", pruned: [] };

    it.each([
      ["成功提示快照文件名", () => jsonResponse(created), "已生成快照 app-20261126-120000.db"],
      ["失败提示去看日志", () => errorResponse(500, "Internal", "boom"), "备份失败，请查看 logs 目录下的日志"],
    ])("不用展开就能立即备份：%s", async (_, response, text) => {
      mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]), "POST /api/backup/run": response });
      renderPage();
      await screen.findByRole("table");
      const card = screen.getByRole("region", { name: "数据备份" });
      await userEvent.setup().click(within(card).getByRole("button", { name: "立即备份" }));
      expect(await screen.findByText(text)).toBeInTheDocument();
      // 结果走操作提示，不插在备份卡片里
      expect(within(card).queryByText(text)).not.toBeInTheDocument();
    });
  });
});

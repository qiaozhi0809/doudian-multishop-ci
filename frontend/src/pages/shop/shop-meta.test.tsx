import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

/** 店铺页测试统一带上备份快照的空响应，避免每个用例重复登记。 */
function mockPageFetch(routes: Parameters<typeof mockFetch>[0]) {
  return mockFetch({
    "GET /api/backup/snapshots": jsonResponse({ items: [], backups_dir: "", keep: 7 }),
    ...routes,
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/shops"]}>
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

describe("店铺字段展示与编辑", () => {
  it("列表带序号列，按原始顺序编号", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([
        makeShop({ id: 1, name: "店铺甲" }),
        makeShop({ id: 2, name: "店铺乙" }),
      ]),
    });
    renderPage();
    const a = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(a.getByText("1")).toBeInTheDocument();
    expect(within(rowOf("店铺乙")).getByText("2")).toBeInTheDocument();
  });

  it("显示平台店铺名与负责人，为空时显示占位", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([
        makeShop({ id: 1, name: "店铺甲", shop_name: "平台甲店", admin_name: "李四" }),
        makeShop({ id: 2, name: "店铺乙", shop_name: null, admin_name: null }),
      ]),
    });
    renderPage();
    const a = within(await screen.findByRole("row", { name: /店铺甲/ }));
    expect(a.getByText("平台甲店")).toBeInTheDocument();
    expect(a.getByText("李四")).toBeInTheDocument();
    expect(within(rowOf("店铺乙")).getAllByText("暂无").length).toBeGreaterThanOrEqual(2);
  });

  it("窄屏会省略的内容悬停能看全：店铺名、平台店铺名、负责人、代理地址、出口状态", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ shop_name: "平台甲店", admin_name: "李四", egress_status: "changed", egress_ip_pending: "1.2.3.5" })]),
    });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    for (const title of ["店铺甲", "平台甲店", "李四", "代理 1.2.3.4:8000", "出口 IP 已变为 1.2.3.5，需确认"]) {
      expect(row.getByTitle(title)).toBeInTheDocument();
    }
  });

  it("编辑店铺：只 PATCH 改动的字段，旧的不合规卡尾号不改就不挡保存", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲", bank_tail: "**** 1234" })]),
      "PATCH /api/shops/1": jsonResponse(makeShop({ id: 1, name: "新名" })),
    });
    renderPage();
    const user = userEvent.setup();
    const row = within(await screen.findByRole("row", { name: /店铺甲/ }));
    await user.click(row.getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "编辑店铺" }));
    const dialog = await screen.findByRole("dialog");
    const nameInput = within(dialog).getByLabelText("店铺名称");
    await user.clear(nameInput);
    await user.type(nameInput, "新名");
    await user.click(within(dialog).getByRole("button", { name: "保存" }));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(JSON.parse(String(call![1]!.body))).toEqual({ name: "新名" });
    });
  });

  it("收款账户为空时，抽屉里显示「同步收款信息」并触发抓取", async () => {
    const emptyBase = jsonResponse({
      addresses: [], couriers: [], templates: [], accounts: [],
    });
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
      "GET /api/shops/1/base": emptyBase,
      "POST /api/shops/1/profile/scrape": jsonResponse(
        makeShop({ id: 1, bank_name: "示例银行", bank_tail: "4567" }),
      ),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "查看店铺资料" }));
    await user.click(await screen.findByRole("button", { name: "同步收款信息" }));
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            init?.method === "POST" && String(input).includes("/api/shops/1/profile/scrape"),
        ),
      ).toBe(true);
    });
  });

  it("已有收款账户时同步按钮仍可点（作为刷新）", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([
        makeShop({ id: 1, name: "店铺甲", bank_name: "示例银行", bank_tail: "4567" }),
      ]),
      "GET /api/shops/1/base": jsonResponse({
        addresses: [], couriers: [], templates: [], accounts: [],
      }),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "查看店铺资料" }));
    await screen.findByText("**** 4567");
    expect(screen.getByRole("button", { name: "同步收款信息" })).toBeEnabled();
  });

  it("停用已登录的店：先确认，确认后 PATCH enabled=false", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲", status: "active" })]),
      "PATCH /api/shops/1": jsonResponse(makeShop({ id: 1, status: "disabled" })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "停用店铺" }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText("停用店铺「店铺甲」")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
    const confirm = dialog.getByRole("button", { name: "停用店铺" });
    expect(confirm.className).toMatch(/danger/);
    await user.click(confirm);
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(JSON.parse(String(call![1]!.body))).toEqual({ enabled: false });
    });
  });

  it("停用未登录的店：不弹确认，直接 PATCH", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲", status: "needs_login" })]),
      "PATCH /api/shops/1": jsonResponse(makeShop({ id: 1, status: "disabled" })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "停用店铺" }));
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(JSON.parse(String(call![1]!.body))).toEqual({ enabled: false });
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("编辑店铺：标题下写店铺名，卡号尾号与店铺ID不合规时就地报错、不发请求", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(
      within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: "编辑店铺" }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getAllByText("店铺甲").length).toBeGreaterThan(0);
    expect(dialog.getByRole("button", { name: "取消" })).toBeInTheDocument();
    const tail = dialog.getByLabelText(/卡号尾号/);
    expect(tail).toHaveAttribute("maxLength", "4");
    await user.type(tail, "1a2");
    expect(tail).toHaveValue("12");
    await user.type(dialog.getByLabelText(/店铺ID/), "x1");
    await user.click(dialog.getByRole("button", { name: "保存" }));
    expect(await dialog.findByText("卡号尾号是 4 位数字")).toBeInTheDocument();
    expect(dialog.getByText("店铺ID是 1 到 20 位数字")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });
});

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

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

let restore: () => void;
beforeEach(() => {
  restore = FakeEventSource.install();
});
afterEach(() => restore());

describe("添加店铺的出口区", () => {
  const poolItem = { id: 5, proxy_display: "5.5.5.5:80", expires_at: null, expiry_state: "ok", in_use_by: null, last_checked_at: null, last_check_ip: null };
  const postBody = (fetchMock: ReturnType<typeof mockPageFetch>) =>
    JSON.parse(String(fetchMock.mock.calls.find(([, init]) => init?.method === "POST")![1]?.body));

  async function openAdd() {
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "添加店铺" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("店铺名称"), "新店");
    return { user, dialog };
  }

  it("从池选择：POST 体带 egress.pool_id", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([]),
      "GET /api/proxy-pool": jsonResponse([poolItem]),
      "POST /api/shops": jsonResponse(makeShop({ id: 9, name: "新店" }), 201),
    });
    const { user, dialog } = await openAdd();
    await user.click(within(dialog).getByRole("button", { name: "从池选择" }));
    await user.click(await within(dialog).findByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "5.5.5.5:80 · 不限期" }));
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    expect(postBody(fetchMock)).toEqual({ name: "新店", egress: { mode: "proxy", pool_id: 5 } });
  });

  it("池为空时选从池选择并提交：显示请选择提示，不发请求", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([]),
      "GET /api/proxy-pool": jsonResponse([]),
    });
    const { user, dialog } = await openAdd();
    await user.click(within(dialog).getByRole("button", { name: "从池选择" }));
    expect(await within(dialog).findByText("池里没有可用代理")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    expect(await within(dialog).findByText("请选择池里的代理")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("出口区不填：POST 体没有 egress", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([]),
      "POST /api/shops": jsonResponse(makeShop({ id: 9, name: "新店" }), 201),
    });
    const { user, dialog } = await openAdd();
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    expect(postBody(fetchMock)).toEqual({ name: "新店" });
  });

  it("已有启用店铺在直连：直连选项禁用并说明原因", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 2, name: "直连店", egress_mode: "direct" })]),
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("table");
    await user.click(screen.getByRole("button", { name: "添加店铺" }));
    const dialog = await screen.findByRole("dialog");
    const direct = within(dialog).getByRole("button", { name: "直连" });
    expect(direct).toBeDisabled();
    // 原因放在提示气泡里（键盘聚焦外层也能看到），不单独占一条提示条，也不用 title
    expect(within(dialog).queryByText("已有店铺「直连店」使用直连，最多一家店可直连")).toBeNull();
    expect(within(dialog).queryByTitle(/使用直连/)).toBeNull();
    act(() => direct.closest<HTMLElement>("span[tabindex='0']")!.focus());
    expect(await screen.findByRole("tooltip")).toHaveTextContent("已有店铺「直连店」使用直连，最多一家店可直连");
  });

  it("直连店已停用时直连可选", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 2, name: "直连店", egress_mode: "direct", status: "disabled" })]),
    });
    renderPage();
    const user = userEvent.setup();
    await screen.findByRole("table");
    await user.click(screen.getByRole("button", { name: "添加店铺" }));
    expect(within(await screen.findByRole("dialog")).getByRole("button", { name: "直连" })).toBeEnabled();
  });
  it("店铺ID 写进 platform_shop_id；不是数字时就地报错、不发请求", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([]),
      "POST /api/shops": jsonResponse(makeShop({ id: 9, name: "新店" }), 201),
    });
    const { user, dialog } = await openAdd();
    expect(within(dialog).getByRole("button", { name: "取消" })).toBeInTheDocument();
    const idInput = within(dialog).getByLabelText(/店铺ID/);
    await user.type(idInput, "12a");
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    expect(await within(dialog).findByText("店铺ID是 1 到 20 位数字")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
    await user.clear(idInput);
    await user.type(idInput, "100000001");
    await user.click(within(dialog).getByRole("button", { name: "添加店铺" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    expect(postBody(fetchMock)).toEqual({ name: "新店", platform_shop_id: "100000001" });
  });
});

describe("设置出口对话框的池入口", () => {
  it("默认从池选择，选定后 PUT 带 pool_id", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ status: "needs_login", egress_status: "unchecked" })]),
      "GET /api/proxy-pool": jsonResponse([
        { id: 5, proxy_display: "5.5.5.5:80", expires_at: "2026-12-31", expiry_state: "ok", in_use_by: null, last_checked_at: null, last_check_ip: null },
      ]),
      "PUT /api/shops/1/egress": jsonResponse(makeShop()),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "设置出口" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "5.5.5.5:80 · 到期 12-31" }));
    await user.click(within(dialog).getByRole("button", { name: "保存出口" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(true));
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(String(put[1]?.body))).toEqual({ mode: "proxy", pool_id: 5 });
  });

});

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

/** 店铺行「⋯」菜单里的飞鸽消息开关。 */
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

describe("飞鸽消息", () => {
  async function openMenu(user: UserEvent) {
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    return screen.findByRole("menu");
  }
  async function pick(user: UserEvent, item: string) {
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: item }));
  }
  const patchCalls = (fetchMock: ReturnType<typeof mockFetch>) => fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH");
  const patchBody = (fetchMock: ReturnType<typeof mockFetch>) => JSON.parse(String(patchCalls(fetchMock)[0][1]?.body));

  it("菜单项按状态显示，和停用店铺并列", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const menu = await openMenu(userEvent.setup());
    const names = within(menu).getAllByRole("menuitem").map((item) => item.textContent);
    expect(names.slice(-2)).toEqual(["开启飞鸽消息", "停用店铺"]);
    expect(within(menu).queryByRole("menuitem", { name: "关闭飞鸽消息" })).not.toBeInTheDocument();
  });

  it("编辑店铺弹窗里没有开关", async () => {
    mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "编辑店铺");
    const dialog = await screen.findByRole("dialog", { name: "编辑店铺" });
    expect(within(dialog).queryByRole("switch")).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/飞鸽/)).not.toBeInTheDocument();
  });

  it("开启先确认，确认按钮是普通主按钮；确认后发 im_enabled: true", async () => {
    let enabled = false;
    const fetchMock = mockPageFetch({
      "GET /api/shops": () => jsonResponse([makeShop({ im_enabled: enabled })]),
      "PATCH /api/shops/1": () => {
        enabled = true;
        return jsonResponse(makeShop({ im_enabled: true }));
      },
    });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "开启飞鸽消息");
    const confirm = await screen.findByRole("dialog", { name: "开启飞鸽消息 店铺甲" });
    expect(confirm).toHaveAccessibleDescription("开启后会在后台常驻该店飞鸽页面，有多个客服账号的店铺尚未验证");
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(patchCalls(fetchMock)).toHaveLength(0);
    const button = within(confirm).getByRole("button", { name: "开启" });
    expect(button.className).toMatch(/primary/);
    await user.click(button);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patchCalls(fetchMock)).toHaveLength(1);
    expect(patchBody(fetchMock)).toEqual({ im_enabled: true });
    expect(await screen.findByText("店铺甲：已开启飞鸽消息")).toBeInTheDocument();
    expect(within(await openMenu(user)).getByRole("menuitem", { name: "关闭飞鸽消息" })).toBeInTheDocument();
  });

  it("确认框点取消：不发请求", async () => {
    const fetchMock = mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "开启飞鸽消息");
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patchCalls(fetchMock)).toHaveLength(0);
  });

  it("开启失败：原因留在确认框里", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "PATCH /api/shops/1": errorResponse(422, "InvalidRequest", "该店暂时不能开启"),
    });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "开启飞鸽消息");
    const confirm = await screen.findByRole("dialog");
    await user.click(within(confirm).getByRole("button", { name: "开启" }));
    expect(await within(confirm).findByText("该店暂时不能开启")).toBeInTheDocument();
  });

  it("关闭不用确认，直接发 im_enabled: false", async () => {
    let enabled = true;
    const fetchMock = mockPageFetch({
      "GET /api/shops": () => jsonResponse([makeShop({ im_enabled: enabled })]),
      "PATCH /api/shops/1": () => {
        enabled = false;
        return jsonResponse(makeShop({ im_enabled: false }));
      },
    });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "关闭飞鸽消息");
    expect(await screen.findByText("店铺甲：已关闭飞鸽消息")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(patchCalls(fetchMock)).toHaveLength(1);
    expect(patchBody(fetchMock)).toEqual({ im_enabled: false });
    await waitFor(() => expect(screen.getByRole("row", { name: /店铺甲/ })).toBeInTheDocument());
    expect(within(await openMenu(user)).getByRole("menuitem", { name: "开启飞鸽消息" })).toBeInTheDocument();
  });

  it("关闭失败：提示原因，菜单项仍是关闭", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ im_enabled: true })]),
      "PATCH /api/shops/1": errorResponse(500, "Internal", "保存失败，请重试"),
    });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "关闭飞鸽消息");
    expect(await screen.findByText("店铺甲：保存失败，请重试")).toBeInTheDocument();
    expect(within(await openMenu(user)).getByRole("menuitem", { name: "关闭飞鸽消息" })).toBeInTheDocument();
  });

  it.each([
    [true, "已开启"],
    [false, "未开启"],
  ])("店铺资料抽屉只读显示飞鸽消息（%s → %s）", async (enabled, text) => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ im_enabled: enabled })]),
      "GET /api/shops/1/base": jsonResponse({ addresses: [], couriers: [], templates: [], accounts: [] }),
    });
    renderPage();
    const user = userEvent.setup();
    await pick(user, "查看店铺资料");
    const drawer = await screen.findByRole("dialog", { name: "店铺资料" });
    expect(within(drawer).getByText("飞鸽消息").closest("li")).toHaveTextContent(text);
    expect(within(drawer).queryByRole("switch")).not.toBeInTheDocument();
  });
});

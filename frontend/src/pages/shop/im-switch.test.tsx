import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FakeEventSource } from "@/test/fake-event-source";
import { makeShop } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

/** 编辑店铺弹窗里的「接收飞鸽消息」开关。 */
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

describe("接收飞鸽消息", () => {
  async function openEditDialog() {
    const user = userEvent.setup();
    await user.click(within(await screen.findByRole("row", { name: /店铺甲/ })).getByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "编辑店铺" }));
    return { user, dialog: await screen.findByRole("dialog", { name: "编辑店铺" }) };
  }
  const patchCalls = (fetchMock: ReturnType<typeof mockFetch>) => fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH");

  it("打开飞鸽开关先确认", async () => {
    let enabled = false;
    const fetchMock = mockPageFetch({
      "GET /api/shops": () => jsonResponse([makeShop({ im_enabled: enabled })]),
      "PATCH /api/shops/1": () => {
        enabled = true;
        return jsonResponse(makeShop({ im_enabled: true }));
      },
    });
    renderPage();
    const { user, dialog } = await openEditDialog();
    const toggle = within(dialog).getByRole("switch", { name: "接收飞鸽消息" });
    expect(toggle).not.toBeChecked();
    await user.click(toggle);
    const confirm = await screen.findByRole("dialog", { name: "接收飞鸽消息" });
    expect(confirm).toHaveAccessibleDescription("开启后会在后台常驻该店飞鸽页面，有多个客服账号的店铺尚未验证");
    expect(toggle).not.toBeChecked();
    expect(patchCalls(fetchMock)).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "开启" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "接收飞鸽消息" })).not.toBeInTheDocument());
    expect(patchCalls(fetchMock)).toHaveLength(1);
    expect(JSON.parse(String(patchCalls(fetchMock)[0][1]?.body))).toEqual({ im_enabled: true });
    expect(toggle).toBeChecked();
  });

  it("确认框点取消：不发请求，开关保持关闭，编辑弹窗还在", async () => {
    const fetchMock = mockPageFetch({ "GET /api/shops": jsonResponse([makeShop()]) });
    renderPage();
    const { user, dialog } = await openEditDialog();
    const toggle = within(dialog).getByRole("switch", { name: "接收飞鸽消息" });
    await user.click(toggle);
    const confirm = await screen.findByRole("dialog", { name: "接收飞鸽消息" });
    await user.click(within(confirm).getByRole("button", { name: "取消" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "接收飞鸽消息" })).not.toBeInTheDocument());
    expect(screen.getByRole("dialog", { name: "编辑店铺" })).toBeInTheDocument();
    expect(toggle).not.toBeChecked();
    expect(patchCalls(fetchMock)).toHaveLength(0);
  });

  it("开启失败：原因留在确认框里", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop()]),
      "PATCH /api/shops/1": errorResponse(422, "InvalidRequest", "该店暂时不能开启"),
    });
    renderPage();
    const { user, dialog } = await openEditDialog();
    await user.click(within(dialog).getByRole("switch", { name: "接收飞鸽消息" }));
    const confirm = await screen.findByRole("dialog", { name: "接收飞鸽消息" });
    await user.click(within(confirm).getByRole("button", { name: "开启" }));
    expect(await within(confirm).findByText("该店暂时不能开启")).toBeInTheDocument();
  });

  it("关掉开关不用确认，直接发 im_enabled: false", async () => {
    let enabled = true;
    const fetchMock = mockPageFetch({
      "GET /api/shops": () => jsonResponse([makeShop({ im_enabled: enabled })]),
      "PATCH /api/shops/1": () => {
        enabled = false;
        return jsonResponse(makeShop({ im_enabled: false }));
      },
    });
    renderPage();
    const { user, dialog } = await openEditDialog();
    const toggle = within(dialog).getByRole("switch", { name: "接收飞鸽消息" });
    expect(toggle).toBeChecked();
    await user.click(toggle);
    expect(screen.queryByRole("dialog", { name: "接收飞鸽消息" })).not.toBeInTheDocument();
    await waitFor(() => expect(toggle).not.toBeChecked());
    expect(patchCalls(fetchMock)).toHaveLength(1);
    expect(JSON.parse(String(patchCalls(fetchMock)[0][1]?.body))).toEqual({ im_enabled: false });
  });

  it("关闭失败：原因显示在编辑弹窗里，开关保持打开", async () => {
    mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ im_enabled: true })]),
      "PATCH /api/shops/1": errorResponse(500, "Internal", "保存失败，请重试"),
    });
    renderPage();
    const { user, dialog } = await openEditDialog();
    const toggle = within(dialog).getByRole("switch", { name: "接收飞鸽消息" });
    await user.click(toggle);
    expect(await within(dialog).findByText("保存失败，请重试")).toBeInTheDocument();
    expect(toggle).toBeChecked();
  });
});

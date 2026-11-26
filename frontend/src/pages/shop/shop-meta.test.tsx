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
    expect(within(rowOf("店铺乙")).getAllByText("—")).toHaveLength(2);
  });

  it("编辑店铺：保存时 PATCH 本地别名", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
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

  it("停用店铺：PATCH enabled=false", async () => {
    const fetchMock = mockPageFetch({
      "GET /api/shops": jsonResponse([makeShop({ id: 1, name: "店铺甲" })]),
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
  });
});

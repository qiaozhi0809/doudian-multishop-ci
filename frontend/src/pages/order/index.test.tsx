import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { makeShop, strongOpenSummary } from "@/test/fixtures";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import OrderPage from "./index";

const counts = (n: number) => ({ stock_up: n, exp_ship: n + 1, ship_delay: n + 2, in_aftersale: n + 3 });
const order = (id: number, over: Record<string, unknown> = {}) => ({
  id, shop_id: 1, shop_name: "店铺甲", order_no: `49000000${id}`, platform_status: 2, status: "synced",
  exception_reason: null, amount_cents: 123456, pay_time: "2026-11-20T01:30:00Z", exp_ship_time: "2026-11-22T01:30:00Z",
  items: [{ sku_order_id: null, product_id: null, product_name: "商品甲", sku_spec: null, quantity: 1, price_cents: null }],
  ...over,
});
const page = (items: unknown[], total = items.length, current = 1) =>
  jsonResponse({ items, total, page: current, page_size: 50 });

const shops = [makeShop({ id: 1, name: "店铺甲" }), makeShop({ id: 2, name: "店铺乙" })];
const countsOk = jsonResponse({ shops: [{ shop_id: 1, source: "upstream", counts: counts(5), fetched_at: new Date().toISOString() }] });

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

function renderPage(path = "/orders") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/orders" element={<OrderPage />} />
          <Route path="/shops" element={<h1>店铺页</h1>} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("订单列表页", () => {
  it("还没有任何店铺：引导去店铺页，而不是空表格", async () => {
    mockFetch({ "GET /api/shops": jsonResponse([]) });
    renderPage();
    expect(await screen.findByText("还没有店铺")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "前往店铺页" }));
    expect(await screen.findByRole("heading", { name: "店铺页" })).toBeInTheDocument();
  });

  it("显示计数、数据时间与订单行（金额、状态、商品摘要）", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([
        order(1, { items: [1, 2, 3].map((i) => ({ sku_order_id: null, product_id: null, product_name: i === 1 ? "商品甲" : "商品乙", sku_spec: null, quantity: 1, price_cents: null })) }),
        order(2, { status: "exception", exception_reason: "地址不全", platform_status: 3, amount_cents: 1 }),
      ]),
    });
    renderPage();
    const row = within(await screen.findByRole("row", { name: /490000001/ }));
    expect(row.getByText("¥1,234.56")).toBeInTheDocument();
    expect(row.getByText("待发货")).toBeInTheDocument(); // 平台状态
    expect(row.getByText("待处理")).toBeInTheDocument(); // 本地状态
    expect(row.getByText("商品甲 等 3 件")).toBeInTheDocument();
    const second = within(screen.getByRole("row", { name: /490000002/ }));
    expect(second.getByText("¥0.01")).toBeInTheDocument();
    expect(second.getByText("异常")).toBeInTheDocument();
    expect(await screen.findByText(/数据时间/)).toBeInTheDocument();
    expect(screen.getByText("24 小时内须发")).toBeInTheDocument();
  });

  it("部分店铺计数失败：显示 N 家店未取到并可展开原因，合计不含失败店", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders": page([]),
      "GET /api/orders/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", counts: counts(5) },
          { shop_id: 2, source: "error", error: "出口不通，请检查代理是否到期或更换代理" },
        ],
      }),
    });
    renderPage();
    expect(await screen.findByText("1 家店未取到")).toBeInTheDocument();
    expect(screen.getByText("合计不含未取到的店铺")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByText(/店铺乙：出口不通/)).toBeInTheDocument();
  });

  it("未取到的店已在顶部横条（登录 / 出口 / 风控）时不再提示；其他原因的店照常提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders": page([]),
      "GET /api/orders/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "error", error: "平台接口报错" },
          { shop_id: 2, source: "error", error: "出口不通，请检查代理是否到期或更换代理" },
        ],
      }),
      "GET /api/notifications/summary": jsonResponse(strongOpenSummary([{ shopId: 2, kinds: ["egress_unreachable"] }])),
    });
    renderPage();
    expect(await screen.findByText("1 家店未取到")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "查看原因" }));
    expect(screen.getByText(/店铺甲：平台接口报错/)).toBeInTheDocument();
    expect(screen.queryByText(/店铺乙：出口不通/)).not.toBeInTheDocument();
  });

  it("未取到的店都已在顶部横条时整条提示不显示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders": page([]),
      "GET /api/orders/counts": jsonResponse({
        shops: [
          { shop_id: 1, source: "upstream", counts: counts(5) },
          { shop_id: 2, source: "error", error: "登录失效" },
        ],
      }),
      "GET /api/notifications/summary": jsonResponse(strongOpenSummary([{ shopId: 2, kinds: ["login_expired"] }])),
    });
    renderPage();
    expect(await screen.findByText("待发货")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/家店未取到/)).not.toBeInTheDocument());
  });

  it("所有店铺计数都失败：只提示未取到，不显示任何 0", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders": page([]),
      "GET /api/orders/counts": jsonResponse({ shops: [{ shop_id: 1, source: "error", error: "x" }, { shop_id: 2, source: "error", error: "y" }] }),
    });
    renderPage();
    expect(await screen.findByText("2 家店未取到")).toBeInTheDocument();
    expect(screen.queryByText("待发货")).not.toBeInTheDocument();
  });

  it("本地状态筛选写入 URL、带 status 请求，并回到第 1 页", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)], 120),
    });
    renderPage("/orders?page=3");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("combobox", { name: /本地状态/ }));
    await user.click(await screen.findByRole("option", { name: "已发货" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/orders?status=shipped"));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/orders?status=shipped&page=1&page_size=50"),
    );
  });

  it("分页：每页 50，翻页写入 URL 并请求对应页", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)], 120),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Page 2" }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/orders?page=2"));
    await waitFor(() => expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/orders?page=2&page_size=50"));
    expect(screen.getByText("共 120 单，每页 50 单")).toBeInTheDocument();
  });

  it("计数卡是快捷筛选：点「超时未发」带 quick=ship_delay 请求并回到第 1 页，再点清除", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)], 120),
    });
    renderPage("/orders?page=3");
    const user = userEvent.setup();
    const card = await screen.findByRole("button", { name: /超时未发/ });
    expect(card).toHaveAttribute("aria-pressed", "false");
    await user.click(card);
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/orders?page=1&page_size=50&quick=ship_delay"),
    );
    expect(screen.getByRole("button", { name: /超时未发/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /超时未发/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /超时未发/ })).toHaveAttribute("aria-pressed", "false"));
  });

  it("序号翻页连续：第 2 页第一行是 51", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1), order(2)], 120, 2),
    });
    renderPage("/orders?page=2");
    const first = await screen.findByRole("row", { name: /490000001/ });
    expect(screen.getAllByRole("columnheader")[0]).toHaveTextContent("序号");
    expect(within(first).getAllByRole("cell")[0]).toHaveTextContent("51");
    expect(within(screen.getByRole("row", { name: /490000002/ })).getAllByRole("cell")[0]).toHaveTextContent("52");
  });

  it("点表头排序：写入 URL、带 sort / order 请求服务端并回到第 1 页；默认排序不显示排序状态", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)], 120),
    });
    renderPage("/orders?page=3");
    const user = userEvent.setup();
    await screen.findByRole("row", { name: /490000001/ });
    expect(screen.getByRole("columnheader", { name: /实付/ })).toHaveAttribute("aria-sort", "none");
    expect(screen.queryByRole("button", { name: /商品/ })).toBeNull(); // 长文本列不排序
    await user.click(screen.getByRole("button", { name: /实付/ }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/orders?sort=amount_cents&order=asc"));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/orders?page=1&page_size=50&sort=amount_cents&order=asc"),
    );
    expect(await screen.findByRole("columnheader", { name: /实付/ })).toHaveAttribute("aria-sort", "ascending");
    await user.click(screen.getByRole("button", { name: /实付/ }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/orders?page=1&page_size=50&sort=amount_cents&order=desc"),
    );
  });

  it("手动同步：区分已开始与正在同步", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)]),
      "POST /api/orders/sync": jsonResponse({ started: [1], already_running: [2] }, 202),
    });
    renderPage();
    await userEvent.setup().click(await screen.findByRole("button", { name: "同步订单" }));
    expect(await screen.findByText("已开始同步 1 家店，1 家店正在同步中")).toBeInTheDocument();
  });

  it("订单读取失败：区块内显示原因与重试，计数仍可见", async () => {
    let fail = true;
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": () => (fail ? errorResponse(500, "Internal", "boom") : page([order(1)])),
    });
    renderPage();
    expect(await screen.findByText("读取订单失败，请确认本地服务正常后重试")).toBeInTheDocument();
    expect(await screen.findByText("待发货")).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByRole("row", { name: /490000001/ })).toBeInTheDocument();
  });

  it("没有符合条件的订单：表格内显示空提示", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([]),
    });
    renderPage("/orders?status=exception");
    expect(await screen.findByText("没有符合条件的订单")).toBeInTheDocument();
  });

  it("点击订单号复制，并就地显示已复制", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup(); // setup 会安装自己的剪贴板替身，之后再覆盖
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/orders/counts": countsOk,
      "GET /api/orders": page([order(1)]),
    });
    renderPage();
    await user.click(await screen.findByRole("button", { name: "490000001" }));
    expect(writeText).toHaveBeenCalledWith("490000001");
    expect(await screen.findByText("已复制")).toBeInTheDocument();
  });
});

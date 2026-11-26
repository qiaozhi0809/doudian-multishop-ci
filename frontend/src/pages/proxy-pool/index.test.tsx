import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import ProxyPoolPage from "./index";
import type { PoolItem } from "./hooks/use-proxy-pool";

const item = (over: Partial<PoolItem> = {}): PoolItem => ({
  id: 1, proxy_display: "1.2.3.4:8080", expires_at: "2026-12-31", expiry_state: "ok",
  in_use_by: null, last_checked_at: null, last_check_ip: null, ...over,
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ProxyPoolPage />
    </QueryClientProvider>,
  );
}

const rowOf = (text: string) => within(screen.getByRole("row", { name: new RegExp(text) }));

describe("代理池页", () => {
  it("三种状态：空闲、已用于店铺、已过期", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([
        item({ id: 1, proxy_display: "1.1.1.1:80" }),
        item({ id: 2, proxy_display: "2.2.2.2:80", in_use_by: { shop_id: 3, shop_name: "店A" } }),
        item({ id: 3, proxy_display: "3.3.3.3:80", expiry_state: "expired", expires_at: "2020-01-01" }),
      ]),
    });
    renderPage();
    await screen.findByRole("row", { name: /1\.1\.1\.1/ });
    expect(rowOf("1.1.1.1").getByText("空闲")).toBeInTheDocument();
    expect(rowOf("2.2.2.2").getByText("已用于「店A」")).toBeInTheDocument();
    expect(rowOf("3.3.3.3").getByText("已过期")).toBeInTheDocument();
  });

  it("空池显示引导：带图标的整页空状态和导入按钮", async () => {
    mockFetch({ "GET /api/proxy-pool": jsonResponse([]) });
    renderPage();
    const title = await screen.findByText("代理池是空的");
    expect(title.closest("section")!.querySelector("svg.lucide-network")).not.toBeNull();
    expect(screen.getByRole("button", { name: "导入代理" })).toBeInTheDocument();
  });

  it("读取失败可重试", async () => {
    let fail = true;
    mockFetch({ "GET /api/proxy-pool": () => (fail ? errorResponse(500, "Internal", "boom") : jsonResponse([item()])) });
    renderPage();
    expect(await screen.findByText("读取代理池失败，请确认本地服务已启动后重试")).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("检查结果含 ip_in_use_by 时提示该 IP 已被店铺使用", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([item()]),
      "POST /api/proxy-pool/1/check": jsonResponse({ elapsed_ms: 80, ip: "9.9.9.9", ip_in_use_by: { shop_id: 4, shop_name: "店B" }, reason: null }),
    });
    renderPage();
    await userEvent.setup().click(await screen.findByRole("button", { name: "检查" }));
    expect(await screen.findByText(/该 IP 已被店铺「店B」使用/)).toBeInTheDocument();
  });

  it("检查失败显示原因文案", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([item()]),
      "POST /api/proxy-pool/1/check": jsonResponse({ elapsed_ms: 10000, ip: null, ip_in_use_by: null, reason: "timeout" }),
    });
    renderPage();
    await userEvent.setup().click(await screen.findByRole("button", { name: "检查" }));
    expect(await screen.findByText(/检查超时（10 秒）/)).toBeInTheDocument();
  });

  it("导入：提交前显示行数统计，提交后显示摘要与失败行号", async () => {
    const fetchMock = mockFetch({
      "GET /api/proxy-pool": jsonResponse([]),
      "POST /api/proxy-pool/import": jsonResponse({ added: 1, skipped: 0, failed: 1, failures: [{ line: 2, reason: "端口必须是数字" }] }),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click((await screen.findAllByRole("button", { name: "导入代理" }))[0]);
    const dialog = within(await screen.findByRole("dialog"));
    await user.click(dialog.getByLabelText("代理列表"));
    await user.paste("1.2.3.4|80|u|p|2026-12-31\nbad");
    expect(dialog.getByText("共 2 行，格式正确 1 行，有问题 1 行")).toBeInTheDocument();
    await user.click(dialog.getByRole("button", { name: "导入" }));
    expect(await dialog.findByText("新增 1 条，已存在 0 条，失败 1 条")).toBeInTheDocument();
    expect(dialog.getByText("第 2 行：端口必须是数字")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u) === "/api/proxy-pool/import")!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ text: "1.2.3.4|80|u|p|2026-12-31\nbad" });
  });

  it("编辑：密码留空不改，只发送有改动的字段", async () => {
    const fetchMock = mockFetch({
      "GET /api/proxy-pool": jsonResponse([item()]),
      "PATCH /api/proxy-pool/1": jsonResponse(item({ proxy_display: "1.2.3.4:9090" })),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "编辑代理" }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getAllByPlaceholderText("留空表示不改")).toHaveLength(2);
    const port = dialog.getByLabelText("端口");
    await user.clear(port);
    await user.type(port, "9090");
    await user.click(dialog.getByRole("button", { name: "保存" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ port: 9090 });
  });

  it("删除：确认框点名代理，被占用时显示服务端原因", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([item({ in_use_by: { shop_id: 3, shop_name: "店A" } })]),
      "DELETE /api/proxy-pool/1": errorResponse(409, "ProxyPoolInUse", "代理正被店铺「店A」使用，请先更换该店出口"),
    });
    renderPage();
    const user = userEvent.setup();
    // 行尾只露「检查」，编辑 / 删除在「⋯」里
    await user.click(await screen.findByRole("button", { name: "更多操作" }));
    await user.click(await screen.findByRole("menuitem", { name: "删除代理" }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText("删除代理 1.2.3.4:8080")).toBeInTheDocument();
    const confirm = dialog.getByRole("button", { name: "删除代理" });
    expect(confirm.className).toMatch(/_danger_/);
    await user.click(confirm);
    expect(await dialog.findByText("代理正被店铺「店A」使用，请先更换该店出口")).toBeInTheDocument();
  });

  it("同一代理检查多次只留最新一条提示", async () => {
    let n = 0;
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([item()]),
      "POST /api/proxy-pool/1/check": () =>
        jsonResponse(
          n++ === 0
            ? { elapsed_ms: 10000, ip: null, ip_in_use_by: null, reason: "timeout" }
            : { elapsed_ms: 80, ip: "9.9.9.9", ip_in_use_by: null, reason: null },
        ),
    });
    renderPage();
    const user = userEvent.setup();
    expect(await screen.findByRole("row", { name: /1\.2\.3\.4/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "删除" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "检查" }));
    expect(await screen.findByText(/检查超时/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "检查" }));
    expect(await screen.findByText(/检查通过/)).toBeInTheDocument();
    expect(screen.queryByText(/检查超时/)).toBeNull();
  });
});

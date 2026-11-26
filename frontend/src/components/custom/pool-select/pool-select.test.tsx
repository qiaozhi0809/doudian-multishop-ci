import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { PoolSelect } from "./pool-select";

const base = { expires_at: "2026-12-31", expiry_state: "ok", in_use_by: null, last_checked_at: null, last_check_ip: null };

function renderSelect(onChange = vi.fn(), error?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PoolSelect value={null} onChange={onChange} error={error} />
    </QueryClientProvider>,
  );
  return onChange;
}

describe("PoolSelect", () => {
  it("只列出可用项，选择后回传 id", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([
        { ...base, id: 1, proxy_display: "1.1.1.1:80" },
        { ...base, id: 2, proxy_display: "2.2.2.2:80", in_use_by: { shop_id: 3, shop_name: "店A" } },
        { ...base, id: 3, proxy_display: "3.3.3.3:80", expires_at: null },
      ]),
    });
    const onChange = renderSelect();
    const user = userEvent.setup();
    const trigger = await screen.findByRole("combobox");
    await user.click(trigger);
    expect(await screen.findByRole("option", { name: "1.1.1.1:80 · 到期 12-31" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /2\.2\.2\.2/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "3.3.3.3:80 · 不限期" }));
    expect(onChange).toHaveBeenCalledWith(3);
  });

  it("没有可用代理时提示", async () => {
    mockFetch({ "GET /api/proxy-pool": jsonResponse([]) });
    renderSelect();
    expect(await screen.findByText("池里没有可用代理")).toBeInTheDocument();
  });

  it("字段错误以红字报错（role=alert），不是灰色说明", async () => {
    mockFetch({ "GET /api/proxy-pool": jsonResponse([{ ...base, id: 1, proxy_display: "1.1.1.1:80" }]) });
    renderSelect(vi.fn(), "请选择池里的代理");
    expect(await screen.findByRole("alert")).toHaveTextContent("请选择池里的代理");
  });

  it("读取失败用提示条", async () => {
    mockFetch({ "GET /api/proxy-pool": errorResponse(500, "Internal", "boom") });
    renderSelect();
    expect(await screen.findByText("读取代理池失败，请稍后重试")).toBeInTheDocument();
  });
});

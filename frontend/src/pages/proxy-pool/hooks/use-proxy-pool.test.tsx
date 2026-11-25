import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { useProxyPool, type PoolItem } from "./use-proxy-pool";

const item = (over: Partial<PoolItem> = {}): PoolItem => ({
  id: 1, proxy_display: "1.2.3.4:8080", expires_at: "2026-12-31", expiry_state: "ok",
  in_use_by: null, last_checked_at: null, last_check_ip: null, ...over,
});

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { ...renderHook(() => useProxyPool(), { wrapper }), invalidate };
}

describe("useProxyPool", () => {
  it("读取列表", async () => {
    mockFetch({ "GET /api/proxy-pool": jsonResponse([item()]) });
    const { result } = setup();
    await waitFor(() => expect(result.current.items).toHaveLength(1));
  });

  it("导入后返回摘要并刷新池与店铺", async () => {
    const summary = { added: 1, skipped: 0, failed: 1, failures: [{ line: 2, reason: "端口必须是数字" }] };
    mockFetch({ "GET /api/proxy-pool": jsonResponse([]), "POST /api/proxy-pool/import": jsonResponse(summary) });
    const { result, invalidate } = setup();
    let out: unknown;
    await act(async () => {
      out = await result.current.importText("x");
    });
    expect(out).toEqual(summary);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["proxyPool"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["shops"] });
  });

  it("导入失败返回服务端原因", async () => {
    mockFetch({ "GET /api/proxy-pool": jsonResponse([]), "POST /api/proxy-pool/import": errorResponse(422, "InvalidRequest", "一次最多导入 500 行") });
    const { result } = setup();
    let out: unknown;
    await act(async () => {
      out = await result.current.importText("x");
    });
    expect(out).toEqual({ error: "一次最多导入 500 行" });
  });

  it("检测后列表刷新，返回检测结果", async () => {
    let checked = false;
    mockFetch({
      "GET /api/proxy-pool": () => jsonResponse([item({ last_check_ip: checked ? "9.9.9.9" : null })]),
      "POST /api/proxy-pool/1/check": () => {
        checked = true;
        return jsonResponse({ elapsed_ms: 120, ip: "9.9.9.9", ip_in_use_by: null, reason: null });
      },
    });
    const { result } = setup();
    await waitFor(() => expect(result.current.items).toHaveLength(1));
    let out: unknown;
    await act(async () => {
      out = await result.current.check(1);
    });
    expect(out).toMatchObject({ ip: "9.9.9.9" });
    await waitFor(() => expect(result.current.items[0].last_check_ip).toBe("9.9.9.9"));
  });

  it("编辑、删除成功返回 ok；失败带原因", async () => {
    mockFetch({
      "GET /api/proxy-pool": jsonResponse([item()]),
      "PATCH /api/proxy-pool/1": jsonResponse(item()),
      "DELETE /api/proxy-pool/1": new Response(null, { status: 204 }),
      "DELETE /api/proxy-pool/2": errorResponse(409, "ProxyPoolInUse", "该代理正被店铺「店A」使用"),
    });
    const { result } = setup();
    let r: unknown;
    await act(async () => {
      r = await result.current.update(1, { port: 80 });
    });
    expect(r).toEqual({ ok: true });
    await act(async () => {
      r = await result.current.remove(1);
    });
    expect(r).toEqual({ ok: true });
    await act(async () => {
      r = await result.current.remove(2);
    });
    expect(r).toEqual({ ok: false, error: "该代理正被店铺「店A」使用" });
    expect(result.current.pendingIds).toEqual([]);
  });
});

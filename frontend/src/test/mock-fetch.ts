type Route = Response | (() => Response);

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export const errorResponse = (status: number, type: string, message = type, shopId: number | null = null) =>
  jsonResponse({ error: { type, message, shop_id: shopId } }, status);

/** 按 "METHOD /path"（不含查询串）路由的 fetch 替身；未登记的请求直接抛错，避免测试悄悄打到真实网络。 */
export function mockFetch(routes: Record<string, Route>) {
  const fn = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input).split("?")[0];
    const key = `${init?.method ?? "GET"} ${url}`;
    const route = routes[key];
    if (!route) throw new Error(`未登记的请求: ${key}`);
    return (typeof route === "function" ? route() : route).clone();
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

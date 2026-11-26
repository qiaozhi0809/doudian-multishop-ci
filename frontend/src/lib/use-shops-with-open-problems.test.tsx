import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { notificationSummaryQuery, useShopsWithOpenProblems } from "./use-shops-with-open-problems";

const SUMMARY = {
  unread: 1,
  strong_open: [
    { shop_id: 1, shop_name: "示例店1", kinds: ["login_expired"], link: null, problems: [{ kind: "login_expired", link: null }] },
    { shop_id: 2, shop_name: "示例店2", kinds: ["ship_deadline"], link: null, problems: [{ kind: "ship_deadline", link: null }] },
  ],
};

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useShopsWithOpenProblems", () => {
  it("读通知摘要，返回有登录 / 出口 / 风控问题的店", async () => {
    mockFetch({ "GET /api/notifications/summary": jsonResponse(SUMMARY) });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useShopsWithOpenProblems(), { wrapper: wrapper(client) });
    await waitFor(() => expect([...result.current]).toEqual([1]));
  });

  it("与通知中心共用同一份摘要缓存，不多发请求", async () => {
    const fetch = mockFetch({ "GET /api/notifications/summary": jsonResponse(SUMMARY) });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => {
        const center = useQuery(notificationSummaryQuery());
        return { center, shops: useShopsWithOpenProblems() };
      },
      { wrapper: wrapper(client) },
    );
    await waitFor(() => expect(result.current.center.isSuccess).toBe(true));
    renderHook(() => useShopsWithOpenProblems(), { wrapper: wrapper(client) });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("摘要读取失败时为空集", async () => {
    mockFetch({});
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useShopsWithOpenProblems(), { wrapper: wrapper(client) });
    expect(result.current.size).toBe(0);
  });
});

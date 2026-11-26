import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import ShopPage from "./index";

/** 店铺页测试统一带上备份快照的空响应，避免每个用例重复登记。 */
export function mockPageFetch(routes: Parameters<typeof mockFetch>[0]) {
  return mockFetch({
    "GET /api/backup/snapshots": jsonResponse({ items: [], backups_dir: "", keep: 7 }),
    ...routes,
  });
}

export function renderPage(path = "/shops") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ShopPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

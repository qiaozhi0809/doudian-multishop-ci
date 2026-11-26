import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { NoticeProvider } from "@/components/custom/notice/notice";
import { FakeEventSource } from "@/test/fake-event-source";
import { jsonResponse, mockFetch } from "@/test/mock-fetch";
import { progressStore } from "./hooks/use-progress";
import type { NotificationItem, StrongOpenShop } from "./logic/notification-view";
import { NotificationBanner, NotificationBell, NotificationCenterProvider } from "./index";

/** 通知中心整体测试共用的数据、渲染与清理。 */
export const item = (over: Partial<NotificationItem> = {}): NotificationItem => ({
  id: 1, kind: "new_order", level: "medium", shop_id: 1, state_key: null, title: "示例店 新增 2 单待发货",
  body: null, link: "/orders?shops=1", count: 2, read_at: null, resolved_at: null,
  created_at: "2026-11-25T08:00:00", updated_at: "2026-11-25T08:00:00", ...over,
});

/** links 给出每个问题各自的链接；不给时都用 link。 */
export const shop = (
  id: number, kinds: StrongOpenShop["kinds"], link: string | null = null, links: Partial<Record<StrongOpenShop["kinds"][number], string>> = {},
): StrongOpenShop => ({
  shop_id: id, shop_name: `示例店${id}`, kinds, link, problems: kinds.map((kind) => ({ kind, link: links[kind] ?? link })),
});

function Where() {
  const l = useLocation();
  return <div data-testid="where">{l.pathname + l.search}</div>;
}

interface Setup {
  items?: NotificationItem[];
  strongOpen?: StrongOpenShop[];
  unread?: number;
  /** 通知总数（默认等于本页条数） */
  total?: number;
}

export function setup({ items = [], strongOpen = [], unread = items.filter((i) => !i.read_at).length, total = items.length }: Setup = {}) {
  const fetch = mockFetch({
    "GET /api/notifications": jsonResponse({ items, total, page: 1, page_size: 20 }),
    "GET /api/notifications/summary": () => jsonResponse({ unread, strong_open: strongOpen }),
    "POST /api/notifications/1/read": new Response(null, { status: 204 }),
    "POST /api/notifications/read-all": new Response(null, { status: 204 }),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <NoticeProvider>
          <NotificationCenterProvider>
            <NotificationBanner />
            <NotificationBell />
          </NotificationCenterProvider>
        </NoticeProvider>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

export const called = (fetch: ReturnType<typeof mockFetch>, path: string) =>
  fetch.mock.calls.some(([url, init]) => String(url).split("?")[0] === path && init?.method === "POST");

export async function openPanel() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "通知" }));
  return { user, panel: await screen.findByRole("dialog", { name: "通知" }) };
}

/** 每个测试文件开头调用一次：清本地存储与进行中任务，装假的 EventSource。 */
export function setupNotificationTests() {
  let restore: () => void;
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    progressStore.reset();
    restore = FakeEventSource.install();
  });
  afterEach(() => {
    vi.useRealTimers();
    restore();
  });
}

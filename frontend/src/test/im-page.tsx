import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import MessagePage from "@/pages/message";
import { FakeEventSource } from "./fake-event-source";
import { makeConversation, makeImStatus, makeMessage } from "./im-fixtures";
import { jsonResponse, mockFetch } from "./mock-fetch";

export const LIST = "GET /api/im/conversations";
export const COUNTS = "GET /api/im/conversations/counts";
export const STATUS = "GET /api/im/status";
export const THREAD = "GET /api/im/conversations/1/conv-test-1/messages";
export const OPEN = "POST /api/im/conversations/1/conv-test-1/open-in-flybird";

export const listPage = (items: unknown[], total = items.length, page = 1) =>
  jsonResponse({ items, total, page, page_size: 50 });
export const thread = (items: unknown[]) => jsonResponse({ shop_id: 1, conversation_id: "conv-test-1", items });

type Routes = Parameters<typeof mockFetch>[0];

export function mockIm(routes: Routes = {}) {
  return mockFetch({
    [LIST]: () => listPage([makeConversation()]),
    [COUNTS]: () => jsonResponse({ unread: 4, waiting: 3, overdue: 1, today: 9 }),
    [STATUS]: () => jsonResponse([makeImStatus()]),
    [THREAD]: () =>
      thread([
        makeMessage(),
        makeMessage({ message_id: "m2", sender_role: "platform", text: "客服已接入" }),
        makeMessage({ message_id: "m3", sender_role: "agent", text: "在的" }),
      ]),
    [OPEN]: () => jsonResponse({ result: "opened" }),
    ...routes,
  });
}

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

export function renderPage(url = "/messages") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <MessagePage />
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

type FetchMock = ReturnType<typeof mockFetch>;
/** 某个路径发出过的请求（完整 URL，按顺序）。 */
export const calls = (fn: FetchMock, path: string) =>
  fn.mock.calls.map(([input]) => String(input)).filter((url) => url.split("?")[0] === path);
export const lastList = (fn: FetchMock) => new URL(calls(fn, "/api/im/conversations").at(-1)!, "http://x").searchParams;
export const row = (name = /测试买家/) => within(screen.getByRole("list", { name: "会话列表" })).findByRole("button", { name });
export const list = () => screen.findByRole("list", { name: "会话列表" });
export const detail = () => screen.getByRole("region", { name: "会话详情" });
export const openRow = async (name = /测试买家/) => {
  await list();
  await userEvent.setup().click(await row(name));
};

/** 每个消息页测试文件开头调用一次：装假的 EventSource，结束时复原计时器与全局替身。 */
export function setupImPageTests() {
  beforeEach(() => {
    FakeEventSource.install();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
}

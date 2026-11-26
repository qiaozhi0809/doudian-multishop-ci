import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FakeEventSource } from "@/test/fake-event-source";
import { errorResponse, jsonResponse, mockFetch } from "@/test/mock-fetch";
import { finding, findingsPage, posts, renderPage, run, shops, started, toasts } from "./reconcile-test-fixtures";

let restoreEvents: () => void;
beforeEach(() => {
  restoreEvents = FakeEventSource.install();
});
afterEach(() => {
  restoreEvents();
  vi.unstubAllGlobals();
});

describe("发货异常页的结果提示与控件", () => {
  it("立即检查完成后结果发到右下角，只发一次", async () => {
    let runRow = run();
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": () => findingsPage([], 0, runRow),
      "POST /api/reconcile/run": () => {
        runRow = run({ run_id: "r2", status: "running", finished_at: null });
        return started();
      },
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "立即检查" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "立即检查" })).toHaveAttribute("aria-busy", "true"),
    );
    expect(toasts().queryByText(/检查/)).not.toBeInTheDocument();

    runRow = run({ run_id: "r2", scanned: 5, finding_count: 1 });
    act(() => FakeEventSource.latest().emit("reconcile_done", { run_id: "r2" }));
    expect(await toasts().findByText("检查完成：扫描 5 单，发现 1 条异常")).toBeInTheDocument();
    expect(screen.getAllByText("检查完成：扫描 5 单，发现 1 条异常")).toHaveLength(1);
  });

  it("上次检查失败时页内保留报错条", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([], 0, run({ status: "failed", scanned: 0, finding_count: 0, error: "店铺 1: 出口不通" })),
    });
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("检查失败：扫描 0 单，发现 0 条异常；店铺 1: 出口不通");
  });

  it("上次检查有店铺没取到时页内保留提醒条", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([], 0, run({ error: "店铺 2: 出口不通" })),
    });
    renderPage();
    expect(await screen.findByText("检查完成：扫描 12 单，发现 2 条异常；店铺 2: 出口不通")).toBeInTheDocument();
  });

  it("触发检查失败时报错发到右下角", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
      "POST /api/reconcile/run": errorResponse(409, "TaskAlreadyRunning", "已有对账批次进行中，请稍候"),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "立即检查" }));
    expect(await toasts().findByRole("alert")).toHaveTextContent("已有对账批次进行中，请稍候");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("标记失败时报错发到右下角", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([finding(1)]),
      "PATCH /api/reconcile/findings/1": errorResponse(404, "NotFound", "对账异常不存在: 1"),
    });
    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "标记已处理" }));
    expect(await toasts().findByRole("alert")).toHaveTextContent("对账异常不存在: 1");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("处理状态是分段切换，选中项写入请求参数", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
    });
    renderPage();
    const group = await screen.findByRole("group", { name: "处理状态" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["全部状态", "未处理", "已处理"]);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(group).getByRole("button", { name: "未处理" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("status=open"))).toBe(true),
    );
  });

  it("检查范围放在立即检查按钮的悬停说明里", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([]),
    });
    renderPage();
    const button = await screen.findByRole("button", { name: "立即检查" });
    expect(screen.queryByText(/检查范围/)).not.toBeInTheDocument();
    fireEvent.focus(button);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("检查范围：最近 30 天");
  });

  it("检查进行中按钮只转圈不置灰，点击不再请求", async () => {
    const fetchMock = mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([], 0, run({ status: "running", finished_at: null })),
    });
    renderPage();
    const button = await screen.findByRole("button", { name: "立即检查" });
    await waitFor(() => expect(button).toHaveAttribute("aria-busy", "true"));
    expect(button).not.toHaveAttribute("disabled");
    await userEvent.setup().click(button);
    expect(posts(fetchMock)).toBe(0);
  });

  it("标记已处理是次要小按钮；已处理的行禁用并说明原因", async () => {
    mockFetch({
      "GET /api/shops": jsonResponse(shops),
      "GET /api/reconcile/findings": findingsPage([finding(1), finding(2, { status: "handled" })]),
    });
    renderPage();
    const [open, handled] = await screen.findAllByRole("button", { name: "标记已处理" });
    expect(open.className).toMatch(/secondary/);
    expect(open.className).toMatch(/\bsm\b|_sm_/);
    expect(open).toBeEnabled();
    expect(handled).toBeDisabled();
    const wrap = handled.parentElement!;
    expect(wrap).toHaveAttribute("tabindex", "0");
    fireEvent.focus(wrap);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("这条已处理");
  });
});

import { useEffect, type ReactNode } from "react";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { NoticeProvider, useNotice, type Notify } from "./notice";

// 离场动画在假计时器下走不完：测试里让提示直接移除
vi.mock("motion/react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("motion/react")>()),
  AnimatePresence: ({ children }: { children?: ReactNode }) => children,
}));

const ref: { notify: Notify | null } = { notify: null };
function Grab() {
  const n = useNotice();
  useEffect(() => {
    ref.notify = n;
  }, [n]);
  return null;
}
const notify = (...args: Parameters<Notify>) => ref.notify?.(...args);
const nav: { go: ((path: string) => void) | null } = { go: null };
function Nav() {
  const navigate = useNavigate();
  useEffect(() => {
    nav.go = (path) => void navigate(path);
  }, [navigate]);
  return null;
}

function renderProvider() {
  render(
    <MemoryRouter>
      <NoticeProvider>
        <Grab />
        <Nav />
      </NoticeProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  ref.notify = null;
});

describe("右下角浮动提示", () => {
  it("同一个 key 只留最新一条，普通提示 4 秒后自动消失", () => {
    vi.useFakeTimers();
    renderProvider();
    act(() => notify("店铺甲：等待扫码", "info", { key: "login:1" }));
    act(() => notify("店铺甲：登录成功", "success", { key: "login:1" }));
    expect(screen.queryByText("店铺甲：等待扫码")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("店铺甲：登录成功");
    act(() => vi.advanceTimersByTime(4100));
    expect(screen.queryByText("店铺甲：登录成功")).not.toBeInTheDocument();
  });

  it("报错用 alert，停留 8 秒", () => {
    vi.useFakeTimers();
    renderProvider();
    act(() => notify("店铺甲：出口不通", "danger"));
    act(() => vi.advanceTimersByTime(4100));
    expect(screen.getByRole("alert")).toHaveTextContent("店铺甲：出口不通");
    act(() => vi.advanceTimersByTime(4000));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("holdMs 指定停留时长", () => {
    vi.useFakeTimers();
    renderProvider();
    act(() => notify("示例店 新增 1 单待发货", "warning", { holdMs: 5000 }));
    act(() => vi.advanceTimersByTime(4900));
    expect(screen.getByText("示例店 新增 1 单待发货")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByText("示例店 新增 1 单待发货")).not.toBeInTheDocument();
  });

  it("persistent 不自动消失，换页面也保留，只能手动关闭", () => {
    vi.useFakeTimers();
    renderProvider();
    act(() => notify("示例店 新增 1 个售后", "danger", { persistent: true }));
    act(() => notify("已同步", "success"));
    act(() => vi.advanceTimersByTime(60_000));
    act(() => notify("已同步", "success"));
    act(() => nav.go?.("/elsewhere"));
    expect(screen.queryByText("已同步")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("示例店 新增 1 个售后");
    act(() => screen.getByRole("button", { name: "关闭提示" }).click());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("超过 4 条时先挤掉最旧的普通提示，常驻的不被挤掉", () => {
    renderProvider();
    act(() => notify("示例店 新增 1 个售后", "danger", { persistent: true }));
    for (const n of [1, 2, 3, 4, 5]) act(() => notify(`普通提示 ${n}`, "success"));
    expect(screen.getByText("示例店 新增 1 个售后")).toBeInTheDocument();
    expect(screen.queryByText("普通提示 1")).not.toBeInTheDocument();
    for (const n of [2, 3, 4, 5]) expect(screen.getByText(`普通提示 ${n}`)).toBeInTheDocument();
  });

  it("事件弹窗：标题与第二行分开，带种类标记", () => {
    renderProvider();
    act(() => notify("示例店 订单同步失败", "warning", { body: "出口不通", event: "system" }));
    expect(screen.getByText("示例店 订单同步失败")).toBeInTheDocument();
    expect(screen.getByText("出口不通")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("data-event", "system");
  });

  it("操作结果提示不带事件标记", () => {
    renderProvider();
    act(() => notify("已同步", "success"));
    expect(screen.getByRole("status")).not.toHaveAttribute("data-event");
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "success");
  });

  it("不在 Provider 里时 useNotice 返回 null（调用方退回页面内提示）", () => {
    render(<Grab />);
    expect(ref.notify).toBeNull();
  });
});

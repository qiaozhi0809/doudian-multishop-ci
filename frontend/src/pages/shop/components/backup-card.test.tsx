import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BackupState } from "../hooks/use-backup";
import { BackupCard } from "./backup-card";

const SNAPSHOT = {
  file_name: "app-20261125-040000.db",
  size_bytes: 307200,
  trigger: "daily",
  actor: null,
  created_at: "2026-11-25T04:00:00Z",
  exists: true,
};

const state = (over: Partial<BackupState> = {}): BackupState => ({
  open: true,
  toggle: vi.fn(),
  list: { items: [SNAPSHOT], backups_dir: "D:/data/backups", keep: 7 },
  pending: false,
  run: vi.fn(),
  loading: false,
  failed: false,
  retry: vi.fn(),
  ...over,
});

const title = () => screen.getByRole("button", { name: "数据备份" });

describe("数据备份卡片", () => {
  it("收起时：标题是可展开的按钮，立即备份一直可用，不显示快照", () => {
    render(<BackupCard backup={state({ open: false })} />);
    expect(title()).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("heading", { name: "数据备份" })).toContainElement(title());
    expect(screen.getByRole("button", { name: "立即备份" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "查看快照" })).not.toBeInTheDocument();
    expect(screen.queryByText(/最近快照/)).not.toBeInTheDocument();
  });

  it("点标题切换展开", async () => {
    const toggle = vi.fn();
    render(<BackupCard backup={state({ open: false, toggle })} />);
    await userEvent.setup().click(title());
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it("展开后显示最近快照、体积与保留份数", () => {
    render(<BackupCard backup={state()} />);
    expect(title()).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/最近快照/)).toBeInTheDocument();
    expect(screen.getByText(/2026-11-25 12:00/)).toBeInTheDocument();
    expect(screen.getByText(/300 KB/)).toBeInTheDocument();
    expect(screen.getByText(/保留最近 7 份/)).toBeInTheDocument();
  });

  it("没有快照时提示暂无快照（卡片内空状态）", () => {
    render(<BackupCard backup={state({ list: { items: [], backups_dir: "x", keep: 7 } })} />);
    expect(screen.getByText("暂无快照")).toHaveClass("panel-empty");
  });

  it("读取中显示骨架，不提前说暂无快照", () => {
    render(<BackupCard backup={state({ list: null, loading: true })} />);
    expect(screen.getByRole("status", { name: "正在读取快照" })).toBeInTheDocument();
    expect(screen.queryByText("暂无快照")).not.toBeInTheDocument();
  });

  it("读取失败给出原因与重试，不当成暂无快照", async () => {
    const retry = vi.fn();
    render(<BackupCard backup={state({ list: null, failed: true, retry })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("读取快照失败，请确认本地服务正常后重试");
    expect(screen.queryByText("暂无快照")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "重新读取" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("点击立即备份触发动作，备份中显示忙碌", async () => {
    const run = vi.fn();
    const { rerender } = render(<BackupCard backup={state({ run })} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "立即备份" }));
    expect(run).toHaveBeenCalledTimes(1);

    rerender(<BackupCard backup={state({ pending: true })} />);
    expect(screen.getByRole("button", { name: /立即备份/ })).toHaveAttribute("aria-busy", "true");
  });
});

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
  created: null,
  failed: false,
  run: vi.fn(),
  ...over,
});

describe("数据备份卡片", () => {
  it("收起时只有说明与展开按钮", () => {
    render(<BackupCard backup={state({ open: false })} />);
    expect(screen.getByRole("button", { name: "查看快照" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "立即备份" })).not.toBeInTheDocument();
  });

  it("展开后显示最近快照、体积与保留份数", () => {
    render(<BackupCard backup={state()} />);
    expect(screen.getByText(/最近快照/)).toBeInTheDocument();
    expect(screen.getByText(/2026-11-25 12:00/)).toBeInTheDocument();
    expect(screen.getByText(/300 KB/)).toBeInTheDocument();
    expect(screen.getByText(/保留最近 7 份/)).toBeInTheDocument();
  });

  it("没有快照时提示可以手动备份", () => {
    render(<BackupCard backup={state({ list: { items: [], backups_dir: "x", keep: 7 } })} />);
    expect(screen.getByText(/暂无快照/)).toBeInTheDocument();
  });

  it("点击立即备份触发动作，备份中禁用按钮", async () => {
    const run = vi.fn();
    const { rerender } = render(<BackupCard backup={state({ run })} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "立即备份" }));
    expect(run).toHaveBeenCalledTimes(1);

    rerender(<BackupCard backup={state({ pending: true })} />);
    expect(screen.getByRole("button", { name: "备份中…" })).toBeDisabled();
  });

  it("成功与失败都有就地提示", () => {
    const { rerender } = render(
      <BackupCard
        backup={state({
          created: {
            file_name: "app-20261125-120000.db",
            size_bytes: 2048,
            trigger: "manual",
            actor: "admin",
            created_at: "2026-11-25T12:00:00Z",
            pruned: [],
          },
        })}
      />,
    );
    expect(screen.getByText(/已生成快照 app-20261125-120000\.db/)).toBeInTheDocument();

    rerender(<BackupCard backup={state({ failed: true })} />);
    expect(screen.getByText(/备份失败，请查看 logs 目录下的日志/)).toBeInTheDocument();
  });
});

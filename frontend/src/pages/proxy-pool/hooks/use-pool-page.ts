import { useRef, useState } from "react";
import { checkNotice, type CheckNotice } from "../logic/pool-status";
import { useProxyPool, type PoolItem } from "./use-proxy-pool";

export type PoolNotice = CheckNotice & { id: number };

/** 页面状态：池数据 + 三个对话框的开关 + 检测结果提示。 */
export function usePoolPage() {
  const pool = useProxyPool();
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<PoolItem | null>(null);
  const [deleting, setDeleting] = useState<PoolItem | null>(null);
  const [notices, setNotices] = useState<PoolNotice[]>([]);
  const nextId = useRef(1);

  const push = (n: CheckNotice) => setNotices((prev) => [...prev, { ...n, id: nextId.current++ }]);

  const check = async (item: PoolItem) => {
    const out = await pool.check(item.id);
    push("error" in out ? { tone: "danger", text: `${item.proxy_display}：${out.error}` } : checkNotice(item.proxy_display, out));
  };

  return {
    pool,
    check,
    notices,
    dismissNotice: (id: number) => setNotices((prev) => prev.filter((n) => n.id !== id)),
    importOpen,
    setImportOpen,
    editing,
    setEditing,
    deleting,
    setDeleting,
  };
}

export type PoolPage = ReturnType<typeof usePoolPage>;

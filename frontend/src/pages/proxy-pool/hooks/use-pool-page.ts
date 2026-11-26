import { useState } from "react";
import { useNoticeQueue } from "@/components/custom/notice/use-notice-queue";
import { checkNotice } from "../logic/pool-status";
import { useProxyPool, type PoolItem } from "./use-proxy-pool";

/** 页面状态：池数据 + 三个对话框的开关 + 检查结果提示（右下角浮动，同一代理只留最新一条）。 */
export function usePoolPage() {
  const pool = useProxyPool();
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<PoolItem | null>(null);
  const [deleting, setDeleting] = useState<PoolItem | null>(null);
  const { notices, notify, dismissNotice } = useNoticeQueue();

  const check = async (item: PoolItem) => {
    const out = await pool.check(item.id);
    const n = "error" in out ? { tone: "danger" as const, text: `${item.proxy_display}：${out.error}` } : checkNotice(item.proxy_display, out);
    notify(`check:${item.id}`, n.tone, n.text);
  };

  return {
    pool,
    check,
    notices,
    dismissNotice,
    importOpen,
    setImportOpen,
    editing,
    setEditing,
    deleting,
    setDeleting,
  };
}

export type PoolPage = ReturnType<typeof usePoolPage>;

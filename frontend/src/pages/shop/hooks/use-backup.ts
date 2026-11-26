import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import type { NoticeTone } from "@/components/custom/notice/notice";

export type BackupSnapshotList = components["schemas"]["BackupSnapshotList"];
export type BackupCreated = components["schemas"]["BackupCreated"];

/**
 * 数据备份（ENG-06）：最近快照与手动触发；每日快照由后端定时任务执行。
 * 默认收起（`enabled: open`）：只有展开时才查询，设置页打开不产生额外请求。
 * 备份结果交给 notify，和店铺页其他操作一样走右下角浮动提示。
 */
export function useBackup(notify: (key: string, tone: NoticeTone, text: string) => void) {
  const [open, setOpen] = useState(false);
  const snapshots = useQuery({
    queryKey: queryKeys.backupSnapshots(),
    queryFn: () => api.get<BackupSnapshotList>("/api/backup/snapshots"),
    enabled: open,
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: () => api.post<BackupCreated>("/api/backup/run"),
    onSuccess: (created) => {
      notify("backup", "success", `已生成快照 ${created.file_name}`);
      void snapshots.refetch();
    },
    onError: () => notify("backup", "danger", "备份失败，请查看 logs 目录下的日志"),
  });
  return {
    open,
    toggle: () => setOpen((value) => !value),
    list: snapshots.data ?? null,
    loading: snapshots.isLoading,
    /** 一份清单都没拿到才算读取失败；刷新失败时继续显示上次的清单。 */
    failed: snapshots.isError && !snapshots.data,
    retry: () => void snapshots.refetch(),
    pending: mutation.isPending,
    run: () => mutation.mutate(),
  };
}

export type BackupState = ReturnType<typeof useBackup>;

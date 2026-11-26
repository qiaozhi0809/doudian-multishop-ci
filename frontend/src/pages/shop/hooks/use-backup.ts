import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useNotice } from "@/components/custom/notice/notice";

export type BackupSnapshotList = components["schemas"]["BackupSnapshotList"];
export type BackupCreated = components["schemas"]["BackupCreated"];

/**
 * 数据备份（ENG-06）：最近快照与手动触发；每日快照由后端定时任务执行。
 * 默认收起（`enabled: open`）：只有展开时才查询，设置页打开不产生额外请求。
 */
export function useBackup() {
  const [open, setOpen] = useState(false);
  // 结果走右下角浮动提示（与店铺页其他操作一致）；没有提示容器时（单测）才在卡内显示
  const notify = useNotice();
  const snapshots = useQuery({
    queryKey: queryKeys.backupSnapshots(),
    queryFn: () => api.get<BackupSnapshotList>("/api/backup/snapshots"),
    enabled: open,
    retry: false,
  });
  const mutation = useMutation({
    mutationFn: () => api.post<BackupCreated>("/api/backup/run"),
    onSuccess: (created) => {
      notify?.(`已生成快照 ${created.file_name}`, "success", { key: "backup" });
      void snapshots.refetch();
    },
    onError: () => notify?.("备份失败，请查看 logs 目录下的日志", "danger", { key: "backup" }),
  });
  return {
    open,
    toggle: () => setOpen((value) => !value),
    list: snapshots.data ?? null,
    pending: mutation.isPending,
    created: notify ? null : (mutation.data ?? null),
    failed: notify ? false : mutation.isError,
    run: () => mutation.mutate(),
  };
}

export type BackupState = ReturnType<typeof useBackup>;

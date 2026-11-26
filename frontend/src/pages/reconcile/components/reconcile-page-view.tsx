import { Alert } from "@/components/arc/alert/alert";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { LoadError } from "@/components/custom/load-error/load-error";
import { NoticeList } from "@/components/custom/notice/notice-list";
import { seqOffset } from "@/lib/list-sort";
import {
  PAGE_SIZE,
  runIncomplete,
  runSummary,
  runTone,
} from "../logic/reconcile-view";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import styles from "../reconcile-page.module.css";
import type { ReconcilePageState } from "../hooks/use-reconcile-page";
import { FindingsTable } from "./findings-table";
import { ReconcileToolbar } from "./reconcile-toolbar";

/** 对账页：店铺就绪判断 → 筛选与触发 → 上次检查没跑全的提醒 → 异常列表。 */
export function ReconcilePageView({ page }: { page: ReconcilePageState }) {
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={SKELETON_LINES.card} />;
  if (page.shopsState === "error") {
    return <LoadError title="读取店铺失败，请确认本地服务已启动后重试" onRetry={page.retryShops} />;
  }
  if (page.shopsState === "empty") {
    return <EmptyNoShops />;
  }

  const state = page.reconcile;
  const data = state.query.data;
  return (
    <div className={styles.page}>
      <ReconcileToolbar
        kind={state.kind}
        onKindChange={state.setKind}
        status={state.status}
        onStatusChange={state.setStatus}
        running={state.running}
        onRun={state.runNow}
      />
      <NoticeList notices={state.notices} onDismiss={state.dismissNotice} />
      {state.run && runIncomplete(state.run) && <Alert tone={runTone(state.run)} title={runSummary(state.run)} />}

      {state.query.isLoading && <Skeleton label="正在读取发货异常" lines={SKELETON_LINES.list} />}
      {state.query.isError && (
        <LoadError title="读取发货异常失败，请确认本地服务正常后重试" onRetry={() => void state.query.refetch()} />
      )}
      {data && (
        <>
          <FindingsTable
            rows={data.items}
            marking={state.marking}
            onMarkHandled={state.markHandled}
            sort={state.sort}
            onSortChange={state.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={state.page} pageSize={PAGE_SIZE} onPageChange={state.setPage} label="发货异常分页" noun="条异常" pageUnit="条" />
        </>
      )}
    </div>
  );
}

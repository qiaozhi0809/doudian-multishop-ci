import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import {
  PAGE_SIZE,
  pageCount,
  runSummary,
  runTone,
} from "../logic/reconcile-view";
import styles from "../reconcile-page.module.css";
import type { ReconcilePageState } from "../hooks/use-reconcile-page";
import { FindingsTable } from "./findings-table";
import { ReconcileToolbar } from "./reconcile-toolbar";

/** 对账页：店铺就绪判断 → 筛选与触发 → 本次结果摘要 → 异常列表。 */
export function ReconcilePageView({ page }: { page: ReconcilePageState }) {
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={4} />;
  if (page.shopsState === "error") {
    return (
      <div className={styles.page}>
        <Alert tone="danger" title="读取店铺失败，请确认本地服务已启动后重试" />
        <div>
          <Button variant="secondary" onClick={page.retryShops}>重新读取</Button>
        </div>
      </div>
    );
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
      <Alert tone={runTone(state.run)} title={runSummary(state.run)} />
      {state.error && (
        <Alert tone="danger" title={state.error} onDismiss={state.clearError} />
      )}

      {state.query.isLoading && <Skeleton label="正在读取发货异常" lines={6} />}
      {state.query.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取发货异常失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void state.query.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <FindingsTable
            rows={data.items}
            marking={state.marking}
            onMarkHandled={state.markHandled}
          />
          <div className={styles.pager}>
            <span>共 {data.total} 条异常，每页 {PAGE_SIZE} 条</span>
            <Pagination
              page={state.page}
              pageCount={pageCount(data.total)}
              onPageChange={state.setPage}
              label="发货异常分页"
            />
          </div>
        </>
      )}
    </div>
  );
}

import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import type { AftersalePageState } from "../hooks/use-aftersale-page";
import { PAGE_SIZE, aggregateAftersaleCounts, pageCount } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";
import { AftersaleMetrics } from "./aftersale-metrics";
import { AftersaleTable } from "./aftersale-table";
import { AftersaleToolbar } from "./aftersale-toolbar";

/** 售后页：没有店铺 → 引导；否则 工具栏 → 计数 → 列表 → 分页。 */
export function AftersalePageView({ page }: { page: AftersalePageState }) {
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={4} />;
  if (page.shopsState === "error") {
    return (
      <div className={styles.page}>
        <Alert tone="danger" title="读取店铺失败，请确认本地服务已启动后重试" />
        <div>
          <Button variant="secondary" onClick={page.retryShops}>
            重新读取
          </Button>
        </div>
      </div>
    );
  }
  if (page.shopsState === "empty") {
    return <EmptyNoShops description="先在「店铺与设置」添加店铺并登录，售后单才会同步到这里" />;
  }

  const data = page.list.data;
  return (
    <div className={styles.page}>
      <AftersaleToolbar
        view={page.view}
        onViewChange={page.setView}
        status={page.status}
        onStatusChange={page.setStatus}
        statusOptions={page.statusOptions}
        syncPending={page.sync.pending}
        onSync={() => void page.sync.sync()}
      />
      <SyncMessageBar message={page.sync.message} onDismiss={page.sync.dismiss} />
      <AftersaleMetrics
        loading={page.counts.isLoading}
        error={page.counts.isError}
        data={page.counts.data ? aggregateAftersaleCounts(page.counts.data) : undefined}
        shopName={page.shopName}
        onRetry={() => void page.counts.refetch()}
      />
      {page.list.isLoading && <Skeleton label="正在读取售后单" lines={6} />}
      {page.list.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取售后单失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void page.list.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <AftersaleTable rows={data.items} />
          <div className={styles.pager}>
            <span>
              共 {data.total} 单，每页 {PAGE_SIZE} 单
            </span>
            <Pagination
              page={page.page}
              pageCount={pageCount(data.total)}
              onPageChange={page.setPage}
              label="售后分页"
            />
          </div>
        </>
      )}
    </div>
  );
}

import { Alert } from "@/components/arc/alert/alert";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import { seqOffset } from "@/lib/list-sort";
import type { AftersalePageState } from "../hooks/use-aftersale-page";
import { PAGE_SIZE, aggregateAftersaleCounts } from "../logic/aftersale-page";
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
    return <EmptyNoShops />;
  }

  const data = page.list.data;
  return (
    <div className={styles.page}>
      <AftersaleToolbar
        view={page.view}
        viewTotals={page.viewTotals}
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
        bannerShopIds={page.bannerShopIds}
        onRetry={() => void page.counts.refetch()}
        cardProps={page.quick.cardProps}
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
          <AftersaleTable
            rows={data.items}
            sort={page.sort}
            onSortChange={page.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={page.page} pageSize={PAGE_SIZE} onPageChange={page.setPage} label="售后分页" noun="单" />
        </>
      )}
    </div>
  );
}

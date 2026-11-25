import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import type { FundPageState } from "../hooks/use-fund-page";
import { UNSETTLED_PAGE_SIZE, unsettledPageCount } from "../logic/fund-page";
import styles from "../fund-page.module.css";
import { FundSummaryCards } from "./fund-summary";
import { BillsTable, MarginTable, UnsettledTable } from "./fund-tables";
import { FundToolbar } from "./fund-toolbar";

function LoadError({ title, onRetry }: { title: string; onRetry: () => void }) {
  return (
    <div className={styles.page}>
      <Alert tone="danger" title={title} />
      <div>
        <Button variant="secondary" onClick={onRetry}>
          重新读取
        </Button>
      </div>
    </div>
  );
}

/** 资金页：没有店铺 → 引导；否则 工具栏 → 概览 → 当前标签页内容。 */
export function FundPageView({ page }: { page: FundPageState }) {
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
    return <EmptyNoShops description="先在「店铺与设置」添加店铺并登录，资金数据才会同步到这里" />;
  }

  return (
    <div className={styles.page}>
      <FundToolbar
        tab={page.tab}
        onTabChange={page.setTab}
        days={page.days}
        onDaysChange={page.setDays}
        syncPending={page.sync.pending}
        onSync={() => void page.sync.sync()}
      />
      <SyncMessageBar message={page.sync.message} onDismiss={page.sync.dismiss} />
      <FundSummaryCards
        loading={page.summary.isLoading}
        error={page.summary.isError}
        data={page.summary.data}
        onRetry={() => void page.summary.refetch()}
      />

      {page.tab === "unsettled" && (
        <>
          {page.unsettled.isLoading && <Skeleton label="正在读取待结算明细" lines={6} />}
          {page.unsettled.isError && (
            <LoadError
              title="读取待结算明细失败，请确认本地服务正常后重试"
              onRetry={() => void page.unsettled.refetch()}
            />
          )}
          {page.unsettled.data && (
            <>
              <UnsettledTable rows={page.unsettled.data.items} />
              <div className={styles.pager}>
                <span>
                  共 {page.unsettled.data.total} 条，每页 {UNSETTLED_PAGE_SIZE} 条
                </span>
                <Pagination
                  page={page.page}
                  pageCount={unsettledPageCount(page.unsettled.data.total)}
                  onPageChange={page.setPage}
                  label="待结算分页"
                />
              </div>
            </>
          )}
        </>
      )}

      {page.tab === "margin" && (
        <>
          {page.margin.isLoading && <Skeleton label="正在读取保证金" lines={4} />}
          {page.margin.isError && (
            <LoadError
              title="读取保证金失败，请确认本地服务正常后重试"
              onRetry={() => void page.margin.refetch()}
            />
          )}
          {page.margin.data && <MarginTable rows={page.margin.data.items} />}
        </>
      )}

      {page.tab === "bills" && (
        <>
          {page.bills.isLoading && <Skeleton label="正在读取账单" lines={4} />}
          {page.bills.isError && (
            <LoadError
              title="读取账单失败（上游不可用时账单无法展示；待结算与保证金不受影响）"
              onRetry={() => void page.bills.refetch()}
            />
          )}
          {page.bills.data && (
            <BillsTable
              shops={page.bills.data.shops}
              days={page.bills.data.days}
              shopName={page.shopName}
            />
          )}
        </>
      )}
    </div>
  );
}

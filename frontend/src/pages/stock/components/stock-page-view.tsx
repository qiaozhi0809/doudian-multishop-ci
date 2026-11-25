import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import type { StockPageState } from "../hooks/use-stock-page";
import { PAGE_SIZE, groupWarehouses, pageCount } from "../logic/stock-page";
import styles from "../stock-page.module.css";
import { StockSummaryCards, WarehouseList } from "./stock-summary";
import { StockTable } from "./stock-table";
import { StockToolbar } from "./stock-toolbar";

/** 库存页：没有店铺 → 引导；否则 工具栏 → 预警汇总 → 仓库 → 列表 → 分页。 */
export function StockPageView({ page }: { page: StockPageState }) {
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
    return <EmptyNoShops description="先在「店铺与设置」添加店铺并登录，库存快照才会同步到这里" />;
  }

  const data = page.list.data;
  return (
    <div className={styles.page}>
      <StockToolbar
        view={page.view}
        onViewChange={page.setView}
        syncPending={page.sync.pending}
        onSync={() => void page.sync.sync()}
      />
      <SyncMessageBar message={page.sync.message} onDismiss={page.sync.dismiss} />
      <StockSummaryCards
        loading={page.summary.isLoading}
        error={page.summary.isError}
        data={page.summary.data}
        onRetry={() => void page.summary.refetch()}
      />
      <WarehouseList
        shops={page.warehouses.data ? groupWarehouses(page.warehouses.data) : []}
        shopName={page.shopName}
        loading={page.warehouses.isLoading}
      />
      {page.list.isLoading && <Skeleton label="正在读取库存" lines={6} />}
      {page.list.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取库存失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void page.list.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <StockTable rows={data.items} />
          <div className={styles.pager}>
            <span>
              共 {data.total} 条库存记录，每页 {PAGE_SIZE} 条
            </span>
            <Pagination
              page={page.page}
              pageCount={pageCount(data.total)}
              onPageChange={page.setPage}
              label="库存分页"
            />
          </div>
        </>
      )}
    </div>
  );
}

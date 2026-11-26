import { ListPager } from "@/components/custom/list-pager/list-pager";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { LoadError } from "@/components/custom/load-error/load-error";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import { seqOffset } from "@/lib/list-sort";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { StockPageState } from "../hooks/use-stock-page";
import { PAGE_SIZE, groupWarehouses } from "../logic/stock-page";
import styles from "../stock-page.module.css";
import { StockSummaryCards, WarehouseList } from "./stock-summary";
import { StockTable } from "./stock-table";
import { StockToolbar } from "./stock-toolbar";

/** 库存页：没有店铺 → 引导；否则 工具栏 → 预警汇总 → 仓库 → 列表 → 分页。 */
export function StockPageView({ page }: { page: StockPageState }) {
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={SKELETON_LINES.card} />;
  if (page.shopsState === "error") return <LoadError title="读取店铺失败，请确认本地服务已启动后重试" onRetry={page.retryShops} />;
  if (page.shopsState === "empty") {
    return <EmptyNoShops />;
  }

  const data = page.list.data;
  return (
    <div className={styles.page}>
      <StockToolbar
        syncPending={page.sync.pending}
        onSync={() => void page.sync.sync()}
      />
      <SyncMessageBar message={page.sync.message} onDismiss={page.sync.dismiss} />
      <StockSummaryCards
        loading={page.summary.isLoading}
        error={page.summary.isError}
        data={page.summary.data}
        onRetry={() => void page.summary.refetch()}
        cardProps={page.quick.cardProps}
      />
      <WarehouseList
        shops={page.warehouses.data ? groupWarehouses(page.warehouses.data) : []}
        shopName={page.shopName}
        loading={page.warehouses.isLoading}
      />
      {page.list.isLoading && <Skeleton label="正在读取库存" lines={SKELETON_LINES.list} />}
      {page.list.isError && (
        <LoadError title="读取库存失败，请确认本地服务正常后重试" onRetry={() => void page.list.refetch()} />
      )}
      {data && (
        <>
          <StockTable
            rows={data.items}
            sort={page.sort}
            onSortChange={page.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={page.page} pageSize={PAGE_SIZE} onPageChange={page.setPage} label="库存分页" noun="条库存记录" pageUnit="条" />
        </>
      )}
    </div>
  );
}

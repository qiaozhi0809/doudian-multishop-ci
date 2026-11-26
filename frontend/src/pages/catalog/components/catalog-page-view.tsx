import { Alert } from "@/components/arc/alert/alert";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { SyncMessageBar } from "@/components/custom/sync-control/sync-control";
import type { CatalogPageState } from "../hooks/use-catalog-page";
import { seqOffset } from "@/lib/list-sort";
import { PAGE_SIZE, mergeGroups } from "../logic/catalog-page";
import styles from "../catalog-page.module.css";
import { CatalogToolbar } from "./catalog-toolbar";
import { ProductCounts, ProductGroups } from "./product-counts";
import { ProductTable } from "./product-table";

/** 商品页：没有店铺 → 引导；否则 工具栏 → 计数 → 分组 → 列表 → 分页。 */
export function CatalogPageView({ page }: { page: CatalogPageState }) {
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
      <CatalogToolbar
        keyword={page.keyword}
        onKeywordChange={page.setKeyword}
        syncPending={page.sync.pending}
        onSync={() => void page.sync.sync()}
      />
      <SyncMessageBar message={page.sync.message} onDismiss={page.sync.dismiss} />
      <ProductCounts
        loading={page.counts.isLoading}
        error={page.counts.isError}
        data={page.counts.data}
        shopName={page.shopName}
        onRetry={() => void page.counts.refetch()}
        cardProps={page.quick.cardProps}
      />
      <ProductGroups
        loading={page.groups.isLoading}
        error={page.groups.isError}
        groups={page.groups.data ? mergeGroups(page.groups.data) : []}
      />
      {page.list.isLoading && <Skeleton label="正在读取商品" lines={6} />}
      {page.list.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取商品失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void page.list.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <ProductTable
            rows={data.items}
            sort={page.sort}
            onSortChange={page.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={page.page} pageSize={PAGE_SIZE} onPageChange={page.setPage} label="商品分页" noun="个商品" pageUnit="个" />
        </>
      )}
    </div>
  );
}

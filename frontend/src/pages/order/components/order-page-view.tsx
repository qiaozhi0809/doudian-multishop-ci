import { Alert } from "@/components/arc/alert/alert";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { seqOffset } from "@/lib/list-sort";
import type { OrderPage } from "../hooks/use-order-page";
import { PAGE_SIZE } from "../logic/order-columns";
import styles from "../order-page.module.css";
import { CountTabs } from "./count-tabs";
import { EmptyOrders } from "./empty-orders";
import { OrderTable } from "./order-table";
import { StatusFilter } from "./status-filter";
import { SyncButton, SyncMessage } from "./sync-button";

/** 订单页：没有店铺 → 引导；否则 工具栏 → 计数 → 表格 → 分页。每个数据区都有加载 / 出错 / 空三种状态。 */
export function OrderPageView({ page }: { page: OrderPage }) {
  const { orders, counts, sync } = page;
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
  if (page.shopsState === "empty") return <EmptyOrders />;

  const data = orders.query.data;
  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <StatusFilter value={orders.status} onChange={orders.setStatus} />
        <SyncButton pending={sync.pending} onClick={() => void sync.sync()} />
      </div>
      <SyncMessage message={sync.message} onDismiss={sync.dismiss} />
      <CountTabs
        state={counts.isLoading ? "loading" : counts.isError ? "error" : "ready"}
        data={counts.data}
        shopName={page.shopName}
        onRetry={() => void counts.refetch()}
        cardProps={orders.quick.cardProps}
      />
      {orders.query.isLoading && <Skeleton label="正在读取订单" lines={6} />}
      {orders.query.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取订单失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void orders.query.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <OrderTable
            rows={data.items}
            sort={orders.sort}
            onSortChange={orders.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={orders.page} pageSize={PAGE_SIZE} onPageChange={orders.setPage} label="订单分页" noun="单" />
        </>
      )}
    </div>
  );
}

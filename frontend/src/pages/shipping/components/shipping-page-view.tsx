import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { PAGE_SIZE, pageCount } from "../logic/ship-columns";
import styles from "../shipping-page.module.css";
import type { ShippingPage } from "../hooks/use-shipping-page";
import { CheckDialog } from "./check-dialog";
import { ShipProgress } from "./ship-progress";
import { ShipTable } from "./ship-table";
import { ShipToolbar } from "./ship-toolbar";

/** 发货台：店铺就绪判断 → 工具栏 → 进度 → 表格 / 分页 → 检查与确认。 */
export function ShippingPageView({ page }: { page: ShippingPage }) {
  const { pool, actions, packageCount } = page;
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
    return <EmptyNoShops description="先在「店铺与设置」添加店铺并扫码登录，待发货订单才会同步到发货台" />;
  }

  const data = pool.query.data;
  return (
    <div className={styles.page}>
      <ShipToolbar
        selectedCount={pool.selected.size}
        packageCount={packageCount}
        busy={actions.checkBusy}
        onCheck={() => actions.openCheck([...pool.selected])}
      />
      {actions.error && (
        <Alert tone="danger" title={actions.error} onDismiss={actions.clearError} />
      )}
      <ShipProgress progress={actions.progress} />

      {pool.query.isLoading && <Skeleton label="正在读取待发货订单" lines={6} />}
      {pool.query.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取待发货订单失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void pool.query.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <ShipTable
            rows={data.items}
            selected={pool.selected}
            allChecked={pool.allChecked}
            onToggle={pool.toggle}
            onToggleAll={pool.toggleAll}
          />
          <div className={styles.pager}>
            <span>共 {data.total} 单，每页 {PAGE_SIZE} 单</span>
            <Pagination
              page={pool.page}
              pageCount={pageCount(data.total)}
              onPageChange={pool.setPage}
              label="待发货订单分页"
            />
          </div>
        </>
      )}

      <CheckDialog
        check={actions.check}
        busy={actions.shipBusy}
        onClose={actions.closeCheck}
        onConfirm={actions.confirm}
      />
    </div>
  );
}

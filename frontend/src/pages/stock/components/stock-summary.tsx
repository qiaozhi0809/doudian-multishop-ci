import { Alert } from "@/components/arc/alert/alert";
import { Badge } from "@/components/arc/badge/badge";
import { Button } from "@/components/arc/button/button";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { ShopWarehouses, StockSummary } from "../logic/stock-page";
import styles from "../stock-page.module.css";

/** 本地快照的库存预警汇总（全部店铺合计）。 */
export function StockSummaryCards({
  loading,
  error,
  data,
  onRetry,
}: {
  loading: boolean;
  error: boolean;
  data: StockSummary | undefined;
  onRetry: () => void;
}) {
  if (loading) return <Skeleton label="正在读取库存汇总" lines={2} />;
  if (error || !data) {
    return (
      <div className={styles.counts}>
        <Alert tone="danger" title="读取库存汇总失败，请确认本地服务正常后重试" />
        <div>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            重新读取
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className={styles.countGrid}>
      <MetricCard label="商品数" value={data.total} tone="neutral" />
      <MetricCard label="库存预警" value={data.alarm_count} tone="warning" />
      <MetricCard label="售罄" value={data.sold_out_count} tone="danger" />
    </div>
  );
}

/** 每店仓库列表（上游）；失败店单独标注。 */
export function WarehouseList({
  shops,
  shopName,
  loading,
}: {
  shops: ShopWarehouses[];
  shopName: (id: number) => string;
  loading: boolean;
}) {
  if (loading) return <Skeleton label="正在读取仓库" lines={1} />;
  // 没有仓库的店不列出：一行「暂无仓库」只是噪音；取数失败的店仍然要标出来
  const rows = shops.filter((shop) => shop.error || shop.items.length > 0);
  if (rows.length === 0) return null;
  return (
    <section className={styles.warehouses} aria-label="仓库列表">
      <h2 className={styles.sectionTitle}>仓库</h2>
      {rows.map((shop) => (
        <div key={shop.shopId} className={styles.warehouseShop}>
          <span className={styles.warehouseShopName}>{shopName(shop.shopId)}</span>
          {shop.error ? (
            <span className={styles.warehouseError}>获取失败：{shop.error}</span>
          ) : (
            shop.items.map((item) => (
              <Badge key={item.warehouse_id} tone="neutral" outline>
                {item.name ?? item.warehouse_id}
              </Badge>
            ))
          )}
        </div>
      ))}
    </section>
  );
}

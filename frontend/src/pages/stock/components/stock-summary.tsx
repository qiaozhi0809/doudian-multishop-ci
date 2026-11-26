import { Badge } from "@/components/arc/badge/badge";
import { MetricCard } from "@/components/arc/metric-card/metric-card";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import type { ShopWarehouses, StockQuick, StockSummary } from "../logic/stock-page";
import styles from "../stock-page.module.css";

/** 本地快照的库存预警汇总（全部店铺合计），也是快捷筛选。 */
export function StockSummaryCards({
  loading,
  error,
  data,
  onRetry,
  cardProps,
}: {
  loading: boolean;
  error: boolean;
  data: StockSummary | undefined;
  onRetry: () => void;
  /** 快捷筛选：预警 / 售罄卡筛下方列表，再点清除；「商品数」卡不对应筛选。 */
  cardProps: (key: StockQuick) => { selected: boolean; onSelect: () => void };
}) {
  if (loading) return <Skeleton label="正在读取库存汇总" lines={2} />;
  if (error || !data) return <LoadError size="sm" title="读取库存汇总失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  return (
    <div className="count-row">
      <MetricCard label="商品数" value={data.total} tone="neutral" />
      <MetricCard label="库存预警" value={data.alarm_count} tone="warning" {...cardProps("alarm")} />
      <MetricCard label="售罄" value={data.sold_out_count} tone="danger" {...cardProps("sold_out")} />
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
  // 仓库来自上游逐店实时读取，慢且多数店为空；读取中不放骨架条（否则卡片与表格之间长时间留一条灰条，读完又常常什么都不显示）
  if (loading) return null;
  // 没有仓库的店不列出：一行「暂无仓库」只是噪音；取数失败的店仍然要标出来
  const rows = shops.filter((shop) => shop.error || shop.items.length > 0);
  if (rows.length === 0) return null;
  return (
    <section className="section" aria-label="仓库列表">
      <h2 className="section-title">仓库</h2>
      <div className={`panel ${styles.warehouses}`}>
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
      </div>
    </section>
  );
}

import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { LoadError } from "@/components/custom/load-error/load-error";
import { CountMeta } from "@/components/custom/shop-failure-alert/count-meta";
import { ShopFailureAlert } from "@/components/custom/shop-failure-alert/shop-failure-alert";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { DashboardPage } from "../hooks/use-dashboard";
import styles from "../dashboard-page.module.css";
import { FundBarsChart, ShipPressureChart } from "./chart-panels";
import { KpiGrid } from "./kpi-grid";
import { ShopRanking } from "./shop-ranking";

/** 仪表盘：多店经营概览。数据全部来自已有聚合接口；没有数据源的指标（GMV、售后率等）不显示，见 dashboard.md。 */
export function DashboardPageView({ page }: { page: DashboardPage }) {
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={SKELETON_LINES.card} />;
  if (page.shopsState === "error") {
    return <LoadError title="读取店铺失败，请确认本地服务已启动后重试" onRetry={page.retryShops} />;
  }
  if (page.shopsState === "empty") {
    return <EmptyNoShops />;
  }

  const { model, sections } = page;
  const failures = [...model.orderFailures, ...model.aftersaleFailures, ...model.productFailures];
  return (
    <div className={styles.page}>
      <CountMeta fetchedAt={model.updatedAt} partial={failures.length > 0} />
      <ShopFailureAlert failures={failures} shopName={page.shopName} bannerShopIds={page.bannerShopIds} />
      <KpiGrid kpis={model.kpis} sections={sections} />
      <div className={styles.chartGrid}>
        <ShipPressureChart bars={model.shipBars} section={sections.orderCounts} />
        <FundBarsChart bars={model.fundBars} section={sections.fund} />
      </div>
      <ShopRanking rows={model.ranking} />
    </div>
  );
}

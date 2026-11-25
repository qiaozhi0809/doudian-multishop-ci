import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { formatBjTime, formatBjTimeSmart } from "@/lib/time-format";
import type { DashboardPage } from "../hooks/use-dashboard";
import styles from "../dashboard-page.module.css";
import { FundBarsChart, ShipPressureChart } from "./chart-panels";
import { SourceFailures } from "./dashboard-sections";
import { KpiGrid } from "./kpi-grid";
import { ShopRanking } from "./shop-ranking";

/** 仪表盘：多店经营概览。数据全部来自已有聚合接口；没有数据源的指标（GMV、售后率等）不显示，见 dashboard.md。 */
export function DashboardPageView({ page }: { page: DashboardPage }) {
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

  const { model, sections } = page;
  const failures = [...model.orderFailures, ...model.aftersaleFailures, ...model.productFailures];
  return (
    <div className={styles.page}>
      <div className={styles.metaRow}>
        {model.updatedAt && (
          <span title={formatBjTime(model.updatedAt)}>数据时间 {formatBjTimeSmart(model.updatedAt)}</span>
        )}
      </div>
      <KpiGrid kpis={model.kpis} sections={sections} />
      <SourceFailures failures={failures} shopName={page.shopName} />
      <div className={styles.chartGrid}>
        <ShipPressureChart bars={model.shipBars} section={sections.orderCounts} />
        <FundBarsChart bars={model.fundBars} section={sections.fund} />
      </div>
      <ShopRanking rows={model.ranking} />
    </div>
  );
}

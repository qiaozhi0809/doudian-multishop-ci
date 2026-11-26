import type { ReactNode } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { BarChart } from "@/components/arc/bar-chart/bar-chart";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatCents } from "@/lib/money-format";
import type { SectionState } from "../hooks/use-dashboard";
import type { ChartBar } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

/** 图表区块：标题在卡片上方（全站区块写法见 styles.css 的 .section / .panel），卡片撑满所在网格列。 */
function ChartFrame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={`section ${styles.chartSection}`}>
      <h2 className="section-title">{title}</h2>
      <div className={`panel ${styles.chartPanel}`}>{children}</div>
    </section>
  );
}

function ChartState({ title, section, empty }: { title: string; section: SectionState; empty: string }) {
  if (section.state === "loading") {
    return (
      <ChartFrame title={title}>
        <Skeleton label={`正在读取${title}`} lines={4} />
      </ChartFrame>
    );
  }
  if (section.state === "error") {
    return (
      <ChartFrame title={title}>
        <div className={styles.chartError}>
          <Alert tone="danger" title={`读取${title}失败，请确认本地服务正常后重试`} />
          <div>
            <Button variant="secondary" size="sm" onClick={section.retry}>
              重新读取
            </Button>
          </div>
        </div>
      </ChartFrame>
    );
  }
  return (
    <ChartFrame title={title}>
      <p className="panel-empty">{empty}</p>
    </ChartFrame>
  );
}

/** 图表数值下方的副标题：画出来的店数。 */
const shopCount = (bars: ChartBar[]) => `${bars.length} 家店`;

/** 各店待发货积压（平台计数，取前 10 家）。 */
export function ShipPressureChart({ bars, section }: { bars: ChartBar[]; section: SectionState }) {
  const title = "发货压力";
  if (section.state !== "ready" || bars.length === 0) {
    return <ChartState title={title} section={section} empty="没有待发货积压" />;
  }
  return (
    <ChartFrame title={title}>
      <BarChart
        data={bars}
        label="各店待发货订单"
        period={shopCount(bars)}
        unit="单"
        averageLabel="店均"
        valueLabel="待发货"
        categoryLabel="店铺"
        height={176}
      />
    </ChartFrame>
  );
}

/** 各店待结算金额（本地资金快照，取前 10 家）。 */
export function FundBarsChart({ bars, section }: { bars: ChartBar[]; section: SectionState }) {
  const title = "待结算分布";
  if (section.state !== "ready" || bars.length === 0) {
    return <ChartState title={title} section={section} empty="没有待结算金额" />;
  }
  return (
    <ChartFrame title={title}>
      <BarChart
        data={bars}
        label="各店待结算金额"
        period={shopCount(bars)}
        averageLabel="店均"
        valueLabel="待结算"
        categoryLabel="店铺"
        height={176}
        formatValue={(value) => formatCents(value)}
      />
    </ChartFrame>
  );
}

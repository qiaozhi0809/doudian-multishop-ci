import type { ReactNode } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { BarChart } from "@/components/arc/bar-chart/bar-chart";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatCents } from "@/lib/money-format";
import type { SectionState } from "../hooks/use-dashboard";
import type { ChartBar } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

function ChartFrame({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className={styles.chartCard}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      <p className={styles.sectionNote}>{description}</p>
      {children}
    </section>
  );
}

function ChartState({
  title,
  description,
  section,
  empty,
}: {
  title: string;
  description: string;
  section: SectionState;
  empty: string;
}) {
  if (section.state === "loading") {
    return (
      <ChartFrame title={title} description={description}>
        <Skeleton label={`正在读取${title}`} lines={4} />
      </ChartFrame>
    );
  }
  if (section.state === "error") {
    return (
      <ChartFrame title={title} description={description}>
        <Alert tone="danger" title={`读取${title}失败，请确认本地服务正常后重试`} />
        <Button variant="secondary" size="sm" onClick={section.retry}>
          重新读取
        </Button>
      </ChartFrame>
    );
  }
  return (
    <ChartFrame title={title} description={description}>
      <p className={styles.muted}>{empty}</p>
    </ChartFrame>
  );
}

/** 各店待发货积压（平台计数，取前 10 家）。 */
export function ShipPressureChart({ bars, section }: { bars: ChartBar[]; section: SectionState }) {
  const title = "发货压力";
  const description = "各店待发货订单（平台计数，取前 10 家）";
  if (section.state !== "ready" || bars.length === 0) {
    return (
      <ChartState title={title} description={description} section={section} empty="当前没有待发货积压" />
    );
  }
  return (
    <ChartFrame title={title} description={description}>
      <BarChart
        data={bars}
        label="各店待发货订单"
        period="按店铺 · 平台实时计数"
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
  const description = "各店待结算金额（本地资金快照，取前 10 家）";
  if (section.state !== "ready" || bars.length === 0) {
    return (
      <ChartState title={title} description={description} section={section} empty="当前没有待结算金额" />
    );
  }
  return (
    <ChartFrame title={title} description={description}>
      <BarChart
        data={bars}
        label="各店待结算金额"
        period="按店铺 · 待结算合计"
        averageLabel="店均"
        valueLabel="待结算"
        categoryLabel="店铺"
        height={176}
        formatValue={(value) => formatCents(value)}
      />
    </ChartFrame>
  );
}

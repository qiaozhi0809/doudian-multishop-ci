import { DashboardPageView } from "./components/dashboard-page-view";
import { useDashboardPage } from "./hooks/use-dashboard";

/** 仪表盘（多店经营概览）：只做装配。 */
export default function DashboardPage() {
  return <DashboardPageView page={useDashboardPage()} />;
}

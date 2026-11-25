import { ReconcilePageView } from "./components/reconcile-page-view";
import { useReconcilePage } from "./hooks/use-reconcile-page";

/** 对账页：只做装配。 */
export default function ReconcilePage() {
  return <ReconcilePageView page={useReconcilePage()} />;
}

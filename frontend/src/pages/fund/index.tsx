import { FundPageView } from "./components/fund-page-view";
import { useFundPage } from "./hooks/use-fund-page";

/** 资金聚合页：只做装配。 */
export default function FundPage() {
  return <FundPageView page={useFundPage()} />;
}

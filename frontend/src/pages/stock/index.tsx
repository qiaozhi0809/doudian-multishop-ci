import { StockPageView } from "./components/stock-page-view";
import { useStockPage } from "./hooks/use-stock-page";

/** 库存聚合页：只做装配。 */
export default function StockPage() {
  return <StockPageView page={useStockPage()} />;
}

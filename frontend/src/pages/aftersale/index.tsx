import { AftersalePageView } from "./components/aftersale-page-view";
import { useAftersalePage } from "./hooks/use-aftersale-page";

/** 售后聚合页：只做装配。 */
export default function AftersalePage() {
  return <AftersalePageView page={useAftersalePage()} />;
}

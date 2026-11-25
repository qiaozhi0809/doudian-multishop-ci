import { CatalogPageView } from "./components/catalog-page-view";
import { useCatalogPage } from "./hooks/use-catalog-page";

/** 商品聚合页：只做装配。 */
export default function CatalogPage() {
  return <CatalogPageView page={useCatalogPage()} />;
}

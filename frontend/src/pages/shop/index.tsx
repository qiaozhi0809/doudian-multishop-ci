import { ShopPageView } from "./components/shop-page-view";
import { useShopPage } from "./hooks/use-shop-page";

/** 店铺管理页：只做装配。 */
export default function ShopPage() {
  return <ShopPageView page={useShopPage()} />;
}

import { ShopPageView } from "./components/shop-page-view";
import { useShopPage } from "./hooks/use-shop-page";

/** 店铺与设置页：只做装配。 */
export default function ShopPage() {
  return <ShopPageView page={useShopPage()} />;
}

import { ShippingPageView } from "./components/shipping-page-view";
import { useShippingPage } from "./hooks/use-shipping-page";

/** 发货台：只做装配。 */
export default function ShippingPage() {
  return <ShippingPageView page={useShippingPage()} />;
}

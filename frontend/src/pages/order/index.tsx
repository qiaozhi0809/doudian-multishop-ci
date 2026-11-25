import { OrderPageView } from "./components/order-page-view";
import { useOrderPage } from "./hooks/use-order-page";

/** 订单列表页：只做装配。 */
export default function OrderPage() {
  return <OrderPageView page={useOrderPage()} />;
}

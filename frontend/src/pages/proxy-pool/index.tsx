import { PoolPageView } from "./components/pool-page-view";
import { usePoolPage } from "./hooks/use-pool-page";

/** 代理池页：只做装配。 */
export default function ProxyPoolPage() {
  return <PoolPageView page={usePoolPage()} />;
}

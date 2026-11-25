import { Store } from "lucide-react";
import { Button } from "@/components/arc/button/button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";

/** 还没有任何店铺：说明原因并给出下一步。 */
export function EmptyShops({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon={<Store size={24} strokeWidth={1.75} aria-hidden="true" />}
      title="还没有店铺"
      description="添加店铺后，设置出口并扫码登录，就能同步订单"
      action={<Button onClick={onAdd}>添加店铺</Button>}
    />
  );
}

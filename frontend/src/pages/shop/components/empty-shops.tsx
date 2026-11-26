import { Store } from "lucide-react";
import { Button } from "@/components/arc/button/button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";

/** 还没有任何店铺：只给标题和「添加店铺」。 */
export function EmptyShops({ onAdd }: { onAdd: () => void }) {
  return (
    <EmptyState
      icon={<Store size={24} strokeWidth={1.75} aria-hidden="true" />}
      title="还没有店铺"
      action={<Button onClick={onAdd}>添加店铺</Button>}
    />
  );
}

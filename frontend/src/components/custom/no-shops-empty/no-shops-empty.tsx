import { Store } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/arc/button/button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";

/** 还没有任何店铺：引导去店铺页添加，而不是显示空表格（四个聚合页共用）。 */
export function NoShopsEmpty({ description }: { description?: string }) {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={<Store size={24} strokeWidth={1.75} aria-hidden="true" />}
      title="还没有店铺"
      description={description ?? "先在「店铺与设置」添加店铺并扫码登录，数据才会同步到这里"}
      action={<Button onClick={() => navigate("/shops")}>前往店铺页</Button>}
    />
  );
}

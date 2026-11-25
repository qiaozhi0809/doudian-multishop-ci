import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Drawer, DrawerContent } from "@/components/arc/drawer/drawer";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";
import { BaseDataSections } from "./base-data-sections";

interface BaseDataDrawerProps {
  shop: ShopRow | null;
  onOpenChange: (open: boolean) => void;
  state: { isLoading: boolean; isError: boolean; data?: components["schemas"]["BaseData"] };
  onRetry: () => void;
}

/** 查看本店基础数据：加载中、出错（可重试）、成功三种状态都有。 */
export function BaseDataDrawer({ shop, onOpenChange, state, onRetry }: BaseDataDrawerProps) {
  return (
    <Drawer open={shop !== null} onOpenChange={onOpenChange}>
      <DrawerContent title="基础数据" description={shop ? `${shop.name} 的发货地址、快递、面单模板与面单账户` : undefined} side="right">
        {state.isLoading && <Skeleton label="正在读取基础数据" lines={6} />}
        {state.isError && (
          <div>
            <Alert tone="danger" title="读取基础数据失败，请重试" />
            <Button variant="secondary" onClick={onRetry}>
              重新读取
            </Button>
          </div>
        )}
        {state.data && <BaseDataSections data={state.data} />}
      </DrawerContent>
    </Drawer>
  );
}

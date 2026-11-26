import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Drawer, DrawerContent } from "@/components/arc/drawer/drawer";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";
import { BaseDataSections } from "./base-data-sections";
import { ShopProfileSections } from "./shop-profile-sections";

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
      <DrawerContent title="基础数据" description={shop?.name} side="right">
        {shop && <ShopProfileSections shop={shop} />}
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

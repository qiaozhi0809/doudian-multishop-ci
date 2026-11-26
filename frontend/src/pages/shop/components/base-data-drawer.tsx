import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Drawer, DrawerContent } from "@/components/arc/drawer/drawer";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { keepOpenOnNotice } from "@/components/custom/notice/keep-open-on-notice";
import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";
import { BaseDataSections } from "./base-data-sections";
import styles from "../shop-page.module.css";
import { ShopProfileSections } from "./shop-profile-sections";

interface BaseDataDrawerProps {
  shop: ShopRow | null;
  onOpenChange: (open: boolean) => void;
  state: { isLoading: boolean; isError: boolean; data?: components["schemas"]["BaseData"] };
  onRetry: () => void;
  onSyncCard?: () => void;
  syncing?: boolean;
}

/** 店铺资料抽屉：店铺信息与收款账户，加上发货资料（加载中、出错可重试、成功三种状态）。 */
export function BaseDataDrawer({
  shop, onOpenChange, state, onRetry, onSyncCard, syncing = false,
}: BaseDataDrawerProps) {
  return (
    <Drawer open={shop !== null} onOpenChange={onOpenChange}>
      <DrawerContent title="店铺资料" description={shop?.name} side="right" onInteractOutside={keepOpenOnNotice}>
        {shop && (
          <ShopProfileSections shop={shop} onSyncCard={onSyncCard} syncing={syncing} />
        )}
        {state.isLoading && <Skeleton label="正在读取发货资料" lines={6} />}
        {state.isError && (
          <div className={styles.page}>
            <Alert tone="danger" title="读取发货资料失败，请重试" />
            <div>
              <Button variant="secondary" onClick={onRetry}>
                重新读取
              </Button>
            </div>
          </div>
        )}
        {state.data && <BaseDataSections data={state.data} />}
      </DrawerContent>
    </Drawer>
  );
}

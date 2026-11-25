import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { ShopPage } from "../hooks/use-shop-page";
import styles from "../shop-page.module.css";
import { AddShopDialog } from "./add-shop-dialog";
import { BaseDataDrawer } from "./base-data-drawer";
import { EgressDialog } from "./egress-dialog";
import { EmptyShops } from "./empty-shops";
import { NoticeList } from "./notice-list";
import { ResumeDialog } from "./resume-dialog";
import { ShopTable } from "./shop-table";

/** 店铺与设置页：加载中 / 出错 / 空 / 列表四种状态，以及各个对话框。 */
export function ShopPageView({ page }: { page: ShopPage }) {
  const { actions, dialogs } = page;
  const rowActions = (shop: { id: number }) => ({
    onLogin: () => void actions.login(shop.id),
    onEgress: () => dialogs.setEgressShopId(shop.id),
    onCheckEgress: () => void actions.checkEgress(shop.id),
    onProbe: () => void actions.probe(shop.id),
    onSyncBase: () => void actions.syncBase(shop.id),
    onViewBase: () => dialogs.setBaseShopId(shop.id),
    onResume: () => dialogs.setResumeShopId(shop.id),
  });

  return (
    <div className={styles.page}>
      {page.status === "ready" && (
        <div className={styles.toolbar}>
          <Button onClick={() => dialogs.setAddOpen(true)}>添加店铺</Button>
        </div>
      )}
      <NoticeList notices={actions.notices} onDismiss={actions.dismissNotice} />
      {page.status === "loading" && <Skeleton label="正在读取店铺" lines={5} />}
      {page.status === "error" && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取店铺失败，请确认本地服务已启动后重试" />
          <div>
            <Button variant="secondary" onClick={page.retry}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {page.status === "empty" && <EmptyShops onAdd={() => dialogs.setAddOpen(true)} />}
      {page.status === "ready" && (
        <ShopTable shops={page.shops} pending={actions.pending} waitingShopIds={actions.waitingShopIds} actionsFor={(s) => rowActions(s)} />
      )}

      <AddShopDialog
        open={dialogs.addOpen}
        onOpenChange={dialogs.setAddOpen}
        pending={actions.pending.includes("add")}
        onSubmit={async (input) => {
          const r = await actions.addShop(input);
          if (r.ok) dialogs.setEgressShopId(r.shop.id);
          return r.ok ? { ok: true } : r;
        }}
      />
      <EgressDialog
        shop={page.egressShop}
        onOpenChange={(open) => !open && dialogs.setEgressShopId(null)}
        pending={page.egressShop ? actions.pending.includes(`egress:${page.egressShop.id}`) : false}
        onSave={(request) => actions.setEgress(page.egressShop!.id, request)}
        onAcceptChange={() => page.egressShop && void actions.checkEgress(page.egressShop.id, true)}
      />
      <ResumeDialog
        shop={page.resumeShop}
        pending={page.resumeShop ? actions.pending.includes(`resume:${page.resumeShop.id}`) : false}
        onOpenChange={(open) => !open && dialogs.setResumeShopId(null)}
        onConfirm={async () => {
          if (!page.resumeShop) return;
          await actions.resume(page.resumeShop.id);
          dialogs.setResumeShopId(null);
        }}
      />
      <BaseDataDrawer
        shop={page.base.shop}
        onOpenChange={(open) => !open && dialogs.setBaseShopId(null)}
        state={page.base.query}
        onRetry={() => void page.base.query.refetch()}
      />
    </div>
  );
}

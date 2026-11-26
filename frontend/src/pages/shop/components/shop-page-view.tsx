import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { LoadError } from "@/components/custom/load-error/load-error";
import { NoticeList } from "@/components/custom/notice/notice-list";
import type { ShopRow } from "@/lib/use-shops";
import { SKELETON_LINES } from "@/lib/skeleton-lines";
import type { ShopPage } from "../hooks/use-shop-page";
import { isLoggedIn } from "../logic/shop-status";
import styles from "../shop-page.module.css";
import { AddShopDialog } from "./add-shop-dialog";
import { BackupCard } from "./backup-card";
import { BaseDataDrawer } from "./base-data-drawer";
import { ConfirmDialog } from "./confirm-dialog";
import { EditShopDialog } from "./edit-shop-dialog";
import { EgressDialog } from "./egress-dialog";
import { EmptyShops } from "./empty-shops";
import { ShopTable } from "./shop-table";

/** 店铺管理页：加载中 / 出错 / 空 / 列表四种状态，以及各个对话框。 */
export function ShopPageView({ page }: { page: ShopPage }) {
  const { actions, dialogs } = page;
  const pendingFor = (action: string, shop: ShopRow | null) => (shop ? actions.pending.includes(`${action}:${shop.id}`) : false);
  /** 停用已登录的店先确认；未登录的直接停用；已停用的直接启用。 */
  const toggle = (shop: ShopRow) => {
    if (shop.status === "disabled") void actions.setEnabled(shop.id, true);
    else if (isLoggedIn(shop)) dialogs.setDisableShopId(shop.id);
    else void actions.setEnabled(shop.id, false);
  };
  /** 飞鸽消息：开启先确认；关闭直接生效。 */
  const toggleIm = (shop: ShopRow) => {
    if (shop.im_enabled) void actions.setIm(shop.id, false);
    else dialogs.setImShopId(shop.id);
  };
  const rowActions = (shop: ShopRow) => ({
    onLogin: () => void actions.login(shop.id),
    onEgress: () => dialogs.setEgressShopId(shop.id),
    onCheckEgress: () => void actions.checkEgress(shop.id),
    onProbe: () => void actions.probe(shop.id),
    onSyncBase: () => void actions.syncBase(shop.id),
    onViewBase: () => dialogs.setBaseShopId(shop.id),
    onResume: () => dialogs.setResumeShopId(shop.id),
    onEdit: () => dialogs.setEditShopId(shop.id),
    onToggleIm: () => toggleIm(shop),
    onToggle: () => toggle(shop),
  });

  return (
    <div className={styles.page}>
      {page.status === "ready" && (
        <div className={styles.toolbar}>
          <Button onClick={() => dialogs.setAddOpen(true)}>添加店铺</Button>
        </div>
      )}
      <NoticeList notices={actions.notices} onDismiss={actions.dismissNotice} />
      {page.status === "loading" && <Skeleton label="正在读取店铺" lines={SKELETON_LINES.list} />}
      {page.status === "error" && (
        <LoadError title="读取店铺失败，请确认本地服务已启动后重试" onRetry={page.retry} />
      )}
      {page.status === "empty" && <EmptyShops onAdd={() => dialogs.setAddOpen(true)} />}
      {page.status === "ready" && (
        <ShopTable shops={page.shops} pending={actions.pending} waitingShopIds={actions.waitingShopIds} actionsFor={(s) => rowActions(s)} highlightId={page.highlightId} claimScroll={page.claimScroll} />
      )}
      <BackupCard backup={page.backup} />

      <AddShopDialog
        open={dialogs.addOpen}
        onOpenChange={dialogs.setAddOpen}
        pending={actions.pending.includes("add")}
        shops={page.allShops}
        onSubmit={async (input) => {
          const r = await actions.addShop(input);
          if (r.ok && !input.egress) dialogs.setEgressShopId(r.shop.id);
          return r.ok ? { ok: true } : r;
        }}
      />
      <EgressDialog
        shop={page.egressShop}
        onOpenChange={(open) => !open && dialogs.setEgressShopId(null)}
        pending={pendingFor("egress", page.egressShop)}
        shops={page.allShops}
        onSave={(request) => actions.setEgress(page.egressShop!.id, request)}
        onAcceptChange={() => page.egressShop && void actions.checkEgress(page.egressShop.id, true)}
      />
      <ConfirmDialog
        shop={page.resumeShop}
        action="恢复店铺"
        confirmLabel="恢复店铺"
        pending={pendingFor("resume", page.resumeShop)}
        onOpenChange={(open) => !open && dialogs.setResumeShopId(null)}
        onConfirm={() => actions.resume(page.resumeShop!.id)}
      />
      <ConfirmDialog
        shop={page.disableShop}
        action="停用店铺"
        confirmLabel="停用店铺"
        danger
        pending={pendingFor("toggle", page.disableShop)}
        onOpenChange={(open) => !open && dialogs.setDisableShopId(null)}
        onConfirm={() => actions.setEnabled(page.disableShop!.id, false, true)}
      />
      <EditShopDialog
        shop={page.editShop}
        pending={pendingFor("edit", page.editShop)}
        onOpenChange={(open) => !open && dialogs.setEditShopId(null)}
        onSubmit={(patch) => actions.updateShop(page.editShop!.id, patch)}
      />
      <ConfirmDialog
        shop={page.imShop}
        action="开启飞鸽消息"
        description="开启后会在后台常驻该店飞鸽页面，有多个客服账号的店铺尚未验证"
        confirmLabel="开启"
        pending={pendingFor("im", page.imShop)}
        onOpenChange={(open) => !open && dialogs.setImShopId(null)}
        onConfirm={() => actions.setIm(page.imShop!.id, true, true)}
      />
      <BaseDataDrawer
        shop={page.base.shop}
        onOpenChange={(open) => !open && dialogs.setBaseShopId(null)}
        state={page.base.query}
        onRetry={() => void page.base.query.refetch()}
        onSyncCard={page.base.shop ? () => void actions.scrapeCard(page.base.shop!.id) : undefined}
        syncing={pendingFor("scrape", page.base.shop)}
      />
    </div>
  );
}

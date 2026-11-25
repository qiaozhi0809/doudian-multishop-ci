import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { EmptyState } from "@/components/arc/empty-state/empty-state";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import type { PoolPage } from "../hooks/use-pool-page";
import styles from "../proxy-pool-page.module.css";
import { DeleteDialog } from "./delete-dialog";
import { EditDialog } from "./edit-dialog";
import { ImportDialog } from "./import-dialog";
import { PoolTable } from "./pool-table";

/** 代理池页：加载中 / 出错 / 空 / 列表，以及导入、编辑、删除对话框。 */
export function PoolPageView({ page }: { page: PoolPage }) {
  const { pool } = page;
  const pendingOf = (id: number | undefined) => id !== undefined && pool.pendingIds.includes(id);
  const importButton = <Button onClick={() => page.setImportOpen(true)}>导入代理</Button>;

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <p className={styles.hint}>代理池里的代理每个只能给一家启用的店铺使用。</p>
        {!pool.loading && !pool.failed && importButton}
      </div>
      {page.notices.length > 0 && (
        <div className={styles.notices} role="status" aria-live="polite">
          {page.notices.map((n) => (
            <Alert key={n.id} tone={n.tone} title={n.text} onDismiss={() => page.dismissNotice(n.id)} />
          ))}
        </div>
      )}
      {pool.loading && <Skeleton label="正在读取代理池" lines={5} />}
      {pool.failed && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取代理池失败，请确认本地服务已启动后重试" />
          <div>
            <Button variant="secondary" onClick={pool.retry}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {!pool.loading && !pool.failed && pool.items.length === 0 && (
        <EmptyState title="代理池是空的" description="导入代理商给的代理后，添加店铺时可以直接选用。" action={importButton} />
      )}
      {pool.items.length > 0 && (
        <PoolTable
          items={pool.items}
          pendingIds={pool.pendingIds}
          onCheck={(item) => void page.check(item)}
          onEdit={page.setEditing}
          onDelete={page.setDeleting}
        />
      )}

      <ImportDialog open={page.importOpen} onOpenChange={page.setImportOpen} pending={pool.importing} onSubmit={pool.importText} />
      <EditDialog
        item={page.editing}
        onOpenChange={(open) => !open && page.setEditing(null)}
        pending={pendingOf(page.editing?.id)}
        onSave={pool.update}
      />
      <DeleteDialog
        item={page.deleting}
        onOpenChange={(open) => !open && page.setDeleting(null)}
        pending={pendingOf(page.deleting?.id)}
        onConfirm={pool.remove}
      />
    </div>
  );
}

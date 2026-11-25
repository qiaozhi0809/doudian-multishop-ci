import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Pagination } from "@/components/arc/pagination/pagination";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { PAGE_SIZE, pageCount } from "../logic/label-columns";
import { componentNotice, printGate, selectedWaybillIds } from "../logic/print-status";
import styles from "../labeling-page.module.css";
import type { LabelPage } from "../hooks/use-label-page";
import { LabelProgress } from "./label-progress";
import { LabelTable } from "./label-table";
import { LabelToolbar } from "./label-toolbar";
import { PreviewDialog } from "./preview-dialog";
import { PrintNotice } from "./print-notice";
import { ReceiverDrawer } from "./receiver-drawer";

/** 打单台：店铺就绪判断 → 工具栏 → 打印状态 → 进度 → 表格 / 分页 → 预览与收件人。 */
export function LabelingPageView({ page }: { page: LabelPage }) {
  const { pool, actions, receiver, print } = page;
  if (page.shopsState === "loading") return <Skeleton label="正在读取店铺" lines={4} />;
  if (page.shopsState === "error") {
    return (
      <div className={styles.page}>
        <Alert tone="danger" title="读取店铺失败，请确认本地服务已启动后重试" />
        <div>
          <Button variant="secondary" onClick={page.retryShops}>重新读取</Button>
        </div>
      </div>
    );
  }
  if (page.shopsState === "empty") {
    return <EmptyNoShops description="先在「店铺与设置」添加店铺并扫码登录，订单才会同步到打单台" />;
  }

  const data = pool.query.data;
  const gate = printGate({
    stage: pool.stage,
    selectedCount: pool.selected.size,
    componentAvailable: print.status ? print.status.available : null,
    busy: actions.previewBusy || actions.executeBusy || print.printing,
  });
  const waybillIds = selectedWaybillIds(pool.selected, pool.rows);
  return (
    <div className={styles.page}>
      <LabelToolbar
        stage={pool.stage}
        onStageChange={pool.setStage}
        selectedCount={pool.selected.size}
        busy={actions.previewBusy || actions.executeBusy}
        onPreview={(mode) => actions.openPreview(mode, [...pool.selected])}
        onPrint={() => print.print(waybillIds)}
        printDisabled={gate.disabled}
        printReason={gate.reason}
        printing={print.printing}
      />
      <PrintNotice
        notice={componentNotice(print.status)}
        summary={print.summary}
        error={print.error}
        onDismissError={print.clearError}
      />
      {actions.error && (
        <Alert tone="danger" title={actions.error} onDismiss={actions.clearError} />
      )}
      <LabelProgress progress={actions.progress} />

      {pool.query.isLoading && <Skeleton label="正在读取订单池" lines={6} />}
      {pool.query.isError && (
        <div className={styles.page}>
          <Alert tone="danger" title="读取订单池失败，请确认本地服务正常后重试" />
          <div>
            <Button variant="secondary" onClick={() => void pool.query.refetch()}>
              重新读取
            </Button>
          </div>
        </div>
      )}
      {data && (
        <>
          <LabelTable
            rows={data.items}
            selected={pool.selected}
            allChecked={pool.allChecked}
            onToggle={pool.toggle}
            onToggleAll={pool.toggleAll}
            onReceiver={(id) => void receiver.open(id)}
            printRows={print.rowsByWaybill}
          />
          <div className={styles.pager}>
            <span>共 {data.total} 单，每页 {PAGE_SIZE} 单</span>
            <Pagination
              page={pool.page}
              pageCount={pageCount(data.total)}
              onPageChange={pool.setPage}
              label="订单池分页"
            />
          </div>
        </>
      )}

      <PreviewDialog
        preview={actions.preview}
        mode={actions.previewMode}
        busy={actions.executeBusy}
        onClose={actions.closePreview}
        onConfirm={actions.execute}
      />
      <ReceiverDrawer
        orderId={receiver.orderId}
        pending={receiver.pending}
        data={receiver.data}
        message={receiver.message}
        onClose={receiver.close}
      />
    </div>
  );
}

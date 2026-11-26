import { Alert } from "@/components/arc/alert/alert";
import { ListPager } from "@/components/custom/list-pager/list-pager";
import { seqOffset } from "@/lib/list-sort";
import { Button } from "@/components/arc/button/button";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { EmptyNoShops } from "@/components/custom/empty-no-shops";
import { PAGE_SIZE } from "../logic/label-columns";
import { componentNotice, printGate, selectedWaybillIds } from "../logic/print-status";
import styles from "../labeling-page.module.css";
import type { LabelPage } from "../hooks/use-label-page";
import { LabelProgress } from "./label-progress";
import { LabelTable } from "./label-table";
import { LabelToolbar } from "./label-toolbar";
import { PreviewDialog } from "./preview-dialog";
import { PrintNotice } from "./print-notice";
import { ReceiverDrawer } from "./receiver-drawer";
import { CheckDialog } from "./check-dialog";
import { ShipProgress } from "./ship-progress";

/** 打单发货：店铺就绪判断 → 阶段与操作 → 打印状态 → 进度 → 表格 / 分页 → 预览、发货检查与收件人。 */
export function LabelingPageView({ page }: { page: LabelPage }) {
  const { pool, actions, receiver, print, ship } = page;
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
    return <EmptyNoShops />;
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
        onShip={() => ship.openCheck([...pool.selected])}
        shipBusy={ship.checkBusy || ship.shipBusy}
      />
      {/* 打印只在「待发货」里做，「待打单」不提示打印组件状态 */}
      <PrintNotice
        notice={pool.stage === "labeled" ? componentNotice(print.status) : null}
        summary={print.summary}
        error={print.error}
        onDismissError={print.clearError}
      />
      {actions.error && (
        <Alert tone="danger" title={actions.error} onDismiss={actions.clearError} />
      )}
      {actions.simulated && (
        <Alert tone="warning" title="演练模式：已记录请求，未真实执行">
          本次执行只写入了审计记录并返回模拟结果；关闭演练模式后重新预览并提交才会真实生效。
        </Alert>
      )}
      {print.simulated && (
        <Alert tone="warning" title="演练模式：已记录打印请求，未真正打印" />
      )}
      {ship.error && <Alert tone="danger" title={ship.error} onDismiss={ship.clearError} />}
      {ship.simulated && (
        <Alert tone="warning" title="演练模式：已记录发货请求，未真实发货">
          本次提交只写入了审计记录并返回模拟结果；关闭演练模式后重新检查并确认才会真实回传平台。
        </Alert>
      )}
      <LabelProgress progress={actions.progress} />
      <ShipProgress progress={ship.progress} />

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
            sort={pool.sort}
            onSortChange={pool.setSort}
            seqOffset={seqOffset(data.page, PAGE_SIZE)}
          />
          <ListPager total={data.total} page={pool.page} pageSize={PAGE_SIZE} onPageChange={pool.setPage} label="订单池分页" noun="单" />
        </>
      )}

      <PreviewDialog
        preview={actions.preview}
        mode={actions.previewMode}
        busy={actions.executeBusy}
        onClose={actions.closePreview}
        onConfirm={actions.execute}
      />
      <CheckDialog check={ship.check} busy={ship.shipBusy} onClose={ship.closeCheck} onConfirm={ship.confirm} />
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

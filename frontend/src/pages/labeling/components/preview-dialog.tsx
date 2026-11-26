import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import { HoldToConfirm } from "@/components/arc/hold-to-confirm/hold-to-confirm";
import { MODE_LABELS, previewTotals, type ExecMode, type PreviewResponse } from "../logic/preview-summary";
import styles from "../labeling-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";

interface PreviewDialogProps {
  preview: PreviewResponse | null;
  mode: ExecMode;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function ShopPlans({ preview }: { preview: PreviewResponse }) {
  if (preview.mode === "void") {
    return (
      <div className={styles.planList}>
        {preview.shops.map((shop) => (
          <div key={shop.shop_id} className={styles.planRow}>
            <strong>{shop.shop_name}</strong>
            <div className={styles.planOrders}>
              {shop.waybills.map((w) => (
                <span key={w.waybill_id} className={styles.planChip}>
                  {w.order_no} · {w.courier_code} {w.waybill_no ?? EMPTY_TEXT}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className={styles.planList}>
      {preview.shops.map((shop) => (
        <div key={shop.shop_id} className={styles.planRow}>
          <strong>{shop.shop_name}</strong>
          <span>
            {shop.courier_name ?? shop.courier_code} · 模板 {shop.template_code} · 账户{" "}
            {shop.ebill_id}/{shop.net_code}
            {shop.account_balance === -1 ? "（月结）" : `（余 ${shop.account_balance ?? EMPTY_TEXT} 张）`}
          </span>
          <span>{shop.ready_order_ids.length} 单</span>
        </div>
      ))}
    </div>
  );
}

/** 预览：按店分组列出将发出的请求与阻断原因；演练模式禁用确认（ui-guidelines 第 7 节）。 */
export function PreviewDialog({ preview, mode, busy, onClose, onConfirm }: PreviewDialogProps) {
  if (preview === null) return null;
  const totals = previewTotals(preview);
  return (
    <Dialog open busy={busy} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent
        title={`预览：${MODE_LABELS[mode]}`}
        description={`影响 ${totals.shops} 家店、${totals.ready} 单；${totals.blocked} 单被跳过`}
      >
        <ShopPlans preview={preview} />
        {preview.blocked.length > 0 && (
          <Alert
            tone="warning"
            title={`${preview.blocked.length} 单会被跳过`}
          >
            <ul className={styles.reasonList}>
              {preview.blocked.map((b) => (
                <li key={`${b.shop_id}-${b.order_id}`}>
                  {b.shop_name} · {b.order_no}：{b.reason}
                </li>
              ))}
            </ul>
          </Alert>
        )}
        {preview.shop_errors.length > 0 && (
          <Alert tone="danger" title="有店铺无法处理">
            <ul className={styles.reasonList}>
              {preview.shop_errors.map((e) => (
                <li key={e.shop_id}>{e.shop_name}：{e.reason}</li>
              ))}
            </ul>
          </Alert>
        )}
        {preview.dry_run && (
          <Alert tone="warning" title="演练模式：本次只记录请求，不发真实写请求" />
        )}
        <div className={styles.dialogFooter}>
          <DialogClose asChild>
            <Button type="button" variant="ghost" disabled={busy}>
              取消
            </Button>
          </DialogClose>
          <HoldToConfirm
            label={`按住确认${MODE_LABELS[mode]}${preview.dry_run ? "（演练）" : ""}`}
            confirmedLabel={`已发起${MODE_LABELS[mode]}`}
            tone={mode === "void" ? "danger" : "accent"}
            onConfirm={onConfirm}
            disabled={busy || totals.ready === 0}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}


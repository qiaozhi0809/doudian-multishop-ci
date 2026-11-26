import { Alert } from "@/components/arc/alert/alert";
import { Dialog } from "@/components/arc/dialog/dialog";
import { AppDialogContent } from "@/components/custom/app-dialog/app-dialog-content";
import { Ban, Printer, Truck } from "lucide-react";
import { MODE_LABELS, previewTotals, type ExecMode, type PreviewResponse } from "../logic/preview-summary";
import styles from "../labeling-page.module.css";
import { EMPTY_TEXT } from "@/lib/empty-text";
import { HoldFooter } from "./hold-footer";
import { ReasonList } from "./reason-list";

/** 按住确认按钮的图标跟着动作走（Arc 默认是垃圾桶）。 */
const MODE_ICONS: Record<ExecMode, typeof Printer> = { obtain: Printer, fetch_and_ship: Truck, void: Ban };

interface PreviewDialogProps {
  preview: PreviewResponse | null;
  mode: ExecMode;
  busy: boolean;
  /** 提交失败的原因，留在对话框里显示。 */
  error: string | null;
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
          <div className={styles.planHead}>
            <strong>{shop.shop_name}</strong>
            <span className={styles.tabular}>{shop.ready_order_ids.length} 单</span>
          </div>
          <span className={styles.planDetail}>
            {shop.courier_name ?? shop.courier_code} · 模板 {shop.template_code} · 账户{" "}
            {shop.ebill_id}/{shop.net_code}
            {shop.account_balance === -1 ? "（月结）" : `（余 ${shop.account_balance ?? EMPTY_TEXT} 张）`}
          </span>
        </div>
      ))}
    </div>
  );
}

/** 预览：按店分组列出将发出的请求与阻断原因；演练模式禁用确认（ui-guidelines 第 7 节）。 */
export function PreviewDialog({ preview, mode, busy, error, onClose, onConfirm }: PreviewDialogProps) {
  if (preview === null) return null;
  const totals = previewTotals(preview);
  const skipped = totals.blocked > 0 ? `；${totals.blocked} 单被跳过` : "";
  const Icon = MODE_ICONS[mode];
  return (
    <Dialog open busy={busy} onOpenChange={(open) => { if (!open) onClose(); }}>
      <AppDialogContent
        size="wide"
        title={`预览：${MODE_LABELS[mode]}`}
        description={`影响 ${totals.shops} 家店、${totals.ready} 单${skipped}`}
      >
        <ShopPlans preview={preview} />
        {preview.blocked.length > 0 && (
          <Alert
            tone="warning"
            title={`${preview.blocked.length} 单会被跳过`}
          >
            <ReasonList
              items={preview.blocked.map((b) => ({ key: `${b.shop_id}-${b.order_id}`, text: `${b.shop_name} · ${b.order_no}：${b.reason}` }))}
            />
          </Alert>
        )}
        {preview.shop_errors.length > 0 && (
          <Alert tone="danger" title="有店铺无法处理">
            <ReasonList items={preview.shop_errors.map((e) => ({ key: e.shop_id, text: `${e.shop_name}：${e.reason}` }))} />
          </Alert>
        )}
        {preview.dry_run && (
          <Alert tone="warning" title="演练模式：本次只记录请求，不发真实写请求" />
        )}
        <HoldFooter
          busy={busy}
          error={error}
          label={`按住确认${MODE_LABELS[mode]}${preview.dry_run ? "（演练）" : ""}`}
          confirmedLabel={`已发起${MODE_LABELS[mode]}`}
          tone={mode === "void" ? "danger" : "accent"}
          icon={<Icon strokeWidth={1.75} />}
          onConfirm={onConfirm}
          disabled={totals.ready === 0}
        />
      </AppDialogContent>
    </Dialog>
  );
}

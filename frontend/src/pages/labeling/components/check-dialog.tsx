import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { Dialog, DialogClose, DialogContent } from "@/components/arc/dialog/dialog";
import { HoldToConfirm } from "@/components/arc/hold-to-confirm/hold-to-confirm";
import { checkSummary, confirmLabel, placeHolderText, type ShipCheck } from "../logic/ship-messages";
import styles from "../labeling-page.module.css";

interface CheckDialogProps {
  check: ShipCheck | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

function detailText(item: Record<string, unknown>, index: number): string {
  const title = typeof item.title === "string" ? item.title : "";
  const message = typeof item.message === "string" ? item.message : "";
  return [title, message].filter(Boolean).join("：") || `确认项 ${index + 1}`;
}

/** 发货前检查结果：二次确认项、阻断与整店错误都在确认前展示（ui-guidelines 第 7 节）。 */
export function CheckDialog({ check, busy, onClose, onConfirm }: CheckDialogProps) {
  if (check === null) return null;
  const placeHolder = placeHolderText(check.shops[0]?.place_holder ?? null);
  return (
    <Dialog open busy={busy} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent title="发货前检查" description={checkSummary(check)}>
        <div className={styles.planList}>
          {check.shops.map((shop) => (
            <div key={shop.shop_id} className={styles.planRow}>
              <strong>{shop.shop_name}</strong>
              <span>通过检查 {shop.total} 单；二次确认项 {shop.double_check_num} 个</span>
              {shop.double_check_num > 0 && (
                <ul className={styles.reasonList}>
                  {shop.double_check_detail.map((item, index) => (
                    <li key={index}>{detailText(item, index)}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
        {placeHolder && <Alert tone="warning" title={placeHolder} />}
        {check.blocked.length > 0 && (
          <Alert tone="warning" title={`${check.blocked.length} 单不可发货，会被跳过`}>
            <ul className={styles.reasonList}>
              {check.blocked.map((b) => (
                <li key={b.order_id}>{b.shop_name} · {b.order_no}：{b.reason}</li>
              ))}
            </ul>
          </Alert>
        )}
        {check.shop_errors.length > 0 && (
          <Alert tone="danger" title="有店铺检查失败，该店订单不会发货">
            <ul className={styles.reasonList}>
              {check.shop_errors.map((e) => (
                <li key={e.shop_id}>{e.shop_name}：{e.reason}</li>
              ))}
            </ul>
          </Alert>
        )}
        {check.double_check_total > 0 && (
          <Alert tone="warning" title="平台要求二次确认" />
        )}
        {check.dry_run && (
          <Alert tone="warning" title="演练模式：本次只记录请求，不发真实发货请求" />
        )}
        <div className={styles.dialogFooter}>
          <DialogClose asChild>
            <Button type="button" variant="ghost" disabled={busy}>
              取消
            </Button>
          </DialogClose>
          <HoldToConfirm
            label={`${confirmLabel(check)}${check.dry_run ? "（演练）" : ""}`}
            confirmedLabel="已提交"
            onConfirm={onConfirm}
            disabled={busy || check.total_orders === 0}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

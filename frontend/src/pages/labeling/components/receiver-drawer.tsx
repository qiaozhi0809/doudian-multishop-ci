import { Alert } from "@/components/arc/alert/alert";
import { Drawer, DrawerContent } from "@/components/arc/drawer/drawer";
import { Skeleton } from "@/components/arc/skeleton/skeleton";
import { formatBjTime } from "@/lib/time-format";
import styles from "../labeling-page.module.css";

interface ReceiverView {
  orderId: number | null;
  pending: boolean;
  data: { name: string | null; phone: string | null; region: string | null; detail: string | null; expire_at: string | null; cached: boolean } | null;
  message: string | null;
  onClose: () => void;
}

/** 收件人抽屉：明文只显示、不入库；截止时间来自平台 expire_time（flows 7.3）。 */
export function ReceiverDrawer({ orderId, pending, data, message, onClose }: ReceiverView) {
  return (
    <Drawer open={orderId !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DrawerContent
        title="收件人"
        description="明文只在本次显示，不写入本地库；每次解密消耗当日额度"
        side="right"
      >
        {pending && <Skeleton label="正在解密收件人" lines={3} />}
        {!pending && message && <Alert tone="warning" title={message} />}
        {!pending && data && (
          <dl className={styles.receiverGrid}>
            <dt>收件人</dt><dd>{data.name ?? "暂无"}</dd>
            <dt>电话</dt><dd className={styles.tabular}>{data.phone ?? "暂无"}</dd>
            <dt>地区</dt><dd>{data.region ?? "暂无"}</dd>
            <dt>详细地址</dt><dd>{data.detail ?? "暂无"}</dd>
            <dt>可用至</dt>
            <dd className={styles.tabular}>
              {data.expire_at ? formatBjTime(data.expire_at) : "暂无"}
              {data.cached ? "（缓存）" : ""}
            </dd>
          </dl>
        )}
      </DrawerContent>
    </Drawer>
  );
}

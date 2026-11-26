import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { LoadError } from "@/components/custom/load-error/load-error";
import { canRestart, type ShopStatus } from "../logic/message-page";
import styles from "../message-page.module.css";

interface ImStatusStripProps {
  /** 不在接收中的已开启店铺。 */
  shops: ShopStatus[];
  failed: boolean;
  onRetry: () => void;
  pending: ReadonlySet<number>;
  onRestart: (shopId: number) => void;
}

/** 接收状态条：一店一行；都在接收时整条不显示。 */
export function ImStatusStrip({ shops, failed, onRetry, pending, onRestart }: ImStatusStripProps) {
  if (failed) return <LoadError size="sm" title="读取接收状态失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  if (shops.length === 0) return null;
  return (
    <div className={styles.stack}>
      {shops.map((shop) => (
        <Alert
          key={shop.shop_id}
          tone={canRestart(shop.state) ? "warning" : "info"}
          title={`${shop.shop_name}：${shop.state_label}`}
        >
          {canRestart(shop.state) ? (
            <Button variant="secondary" size="sm" loading={pending.has(shop.shop_id)} onClick={() => onRestart(shop.shop_id)}>
              重新连接
            </Button>
          ) : undefined}
        </Alert>
      ))}
    </div>
  );
}

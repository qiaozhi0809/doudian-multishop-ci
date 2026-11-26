import { TriangleAlert } from "lucide-react";
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

/** 接收状态条：一店一行、单行高，按钮靠右；都在接收时整条不显示。 */
export function ImStatusStrip({ shops, failed, onRetry, pending, onRestart }: ImStatusStripProps) {
  if (failed) return <LoadError size="sm" title="读取接收状态失败，请确认本地服务正常后重试" onRetry={onRetry} />;
  if (shops.length === 0) return null;
  return (
    <ul className={styles.statusStrip} aria-label="未在接收的店铺">
      {shops.map((shop) => (
        <li
          key={shop.shop_id}
          className={styles.statusLine}
          data-tone={canRestart(shop.state) ? "warning" : "info"}
          aria-label={`${shop.shop_name}：${shop.state_label}`}
        >
          <TriangleAlert size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className={styles.statusShop}>{shop.shop_name}</span>
          <span className={styles.statusLabel}>{shop.state_label}</span>
          {canRestart(shop.state) && (
            <Button
              className={styles.statusAction}
              variant="secondary"
              size="sm"
              loading={pending.has(shop.shop_id)}
              onClick={() => onRestart(shop.shop_id)}
            >
              重新连接
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

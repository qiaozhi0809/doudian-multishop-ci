import { Button } from "@/components/arc/button/button";
import { orEmpty } from "@/lib/empty-text";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../shop-page.module.css";

function Section({
  title, rows, action,
}: {
  title: string;
  rows: [string, string | null | undefined][];
  action?: React.ReactNode;
}) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionHeader}>
        <h3 className="section-title">{title}</h3>
        {action}
      </div>
      <ul className={styles.list}>
        {rows.map(([label, value]) => (
          <li key={label} className={styles.listItem}>
            <span className={styles.listMain}>
              <span>{label}</span>
              <span className={styles.muted}>{orEmpty(value)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface ShopProfileSectionsProps {
  shop: ShopRow;
  onSyncCard?: () => void;
  syncing?: boolean;
}

/**
 * 平台侧固定信息：店铺名/负责人由登录后同步，店铺ID/主体/收款账户平台没有稳定接口，
 * 由「同步收款信息」按钮（已有信息时作为刷新）或「编辑店铺」手工维护。飞鸽消息只读，开关在店铺行「⋯」菜单。
 */
export function ShopProfileSections({ shop, onSyncCard, syncing = false }: ShopProfileSectionsProps) {
  return (
    <>
      <Section
        title="店铺信息"
        rows={[
          ["平台店铺名", shop.shop_name],
          ["店铺ID", shop.platform_shop_id],
          ["主体", shop.entity],
          ["负责人", shop.admin_name],
          ["飞鸽消息", shop.im_enabled ? "已开启" : "未开启"],
        ]}
      />
      <Section
        title="收款账户"
        rows={[
          ["开户行", shop.bank_name],
          ["卡号尾号", shop.bank_tail ? `**** ${shop.bank_tail}` : null],
        ]}
        action={
          onSyncCard ? (
            <Button variant="secondary" size="sm" loading={syncing} onClick={onSyncCard}>
              同步收款信息
            </Button>
          ) : undefined
        }
      />
    </>
  );
}

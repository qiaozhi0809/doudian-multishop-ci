import { Button } from "@/components/arc/button/button";
import styles from "../shipping-page.module.css";

interface ShipToolbarProps {
  selectedCount: number;
  packageCount: number;
  busy: boolean;
  onCheck: () => void;
}

/** 发货入口：先做发货前检查，未勾选 / 检查中时禁用但保持可见。 */
export function ShipToolbar({ selectedCount, packageCount, busy, onCheck }: ShipToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <span className={styles.muted}>
        已选 {selectedCount} 单 · {packageCount} 个包裹
      </span>
      <div className={styles.toolbarActions}>
        <Button onClick={onCheck} disabled={selectedCount === 0 || busy} loading={busy}>
          发货前检查
        </Button>
      </div>
    </div>
  );
}

import { SyncButton } from "@/components/custom/sync-control/sync-control";
import styles from "../stock-page.module.css";

interface ToolbarProps {
  syncPending: boolean;
  onSync: () => void;
}

/** 库存工具栏：同步。筛选用上方的计数卡（预警 / 售罄）。 */
export function StockToolbar({ syncPending, onSync }: ToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <SyncButton pending={syncPending} label="同步库存" onClick={onSync} />
    </div>
  );
}

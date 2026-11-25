import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { SyncButton } from "@/components/custom/sync-control/sync-control";
import { STOCK_VIEWS, isStockView, type StockView } from "../logic/stock-page";
import styles from "../stock-page.module.css";

interface ToolbarProps {
  view: StockView;
  onViewChange: (view: StockView) => void;
  syncPending: boolean;
  onSync: () => void;
}

/** 库存视图（全部 / 只看预警）+ 同步。 */
export function StockToolbar({ view, onViewChange, syncPending, onSync }: ToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <SegmentedControl
        label="库存视图"
        options={[...STOCK_VIEWS]}
        value={view}
        onValueChange={(value) => {
          if (isStockView(value)) onViewChange(value);
        }}
      />
      <SyncButton pending={syncPending} label="同步库存" onClick={onSync} />
    </div>
  );
}

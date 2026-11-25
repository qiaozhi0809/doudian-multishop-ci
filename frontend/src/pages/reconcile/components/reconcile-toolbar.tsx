import { Button } from "@/components/arc/button/button";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Select } from "@/components/arc/select/select";
import {
  KIND_OPTIONS,
  STATUS_OPTIONS,
  isKind,
  isStatus,
  type KindFilter,
  type StatusFilter,
} from "../logic/reconcile-view";
import styles from "../reconcile-page.module.css";

interface ReconcileToolbarProps {
  kind: KindFilter;
  onKindChange: (kind: KindFilter) => void;
  status: StatusFilter;
  onStatusChange: (status: StatusFilter) => void;
  running: boolean;
  onRun: () => void;
}

/** 异常类型 / 处理状态筛选 + 手动触发对账（窗口 30 天，见附录 G.5）。 */
export function ReconcileToolbar(props: ReconcileToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.filters}>
        <SegmentedControl
          label="异常类型"
          options={[...KIND_OPTIONS]}
          value={props.kind}
          onValueChange={(value) => {
            if (isKind(value)) props.onKindChange(value);
          }}
        />
        <Select
          className={styles.filter}
          label="处理状态"
          value={props.status}
          onValueChange={(value) => {
            if (isStatus(value)) props.onStatusChange(value);
          }}
          options={[...STATUS_OPTIONS]}
        />
      </div>
      <div className={styles.actions}>
        <span className={styles.muted}>对账窗口：最近 30 天</span>
        <Button onClick={props.onRun} loading={props.running} disabled={props.running}>
          立即对账
        </Button>
      </div>
    </div>
  );
}

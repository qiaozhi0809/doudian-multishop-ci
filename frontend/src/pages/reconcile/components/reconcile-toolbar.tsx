import { Button } from "@/components/arc/button/button";
import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
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
        <SegmentedControl
          label="处理状态"
          options={[...STATUS_OPTIONS]}
          value={props.status}
          onValueChange={(value) => {
            if (isStatus(value)) props.onStatusChange(value);
          }}
        />
      </div>
      <Tooltip content="检查范围：最近 30 天">
        <Button onClick={props.onRun} loading={props.running}>
          立即检查
        </Button>
      </Tooltip>
    </div>
  );
}

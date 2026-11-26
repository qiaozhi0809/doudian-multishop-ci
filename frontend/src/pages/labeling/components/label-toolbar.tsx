import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Button } from "@/components/arc/button/button";
import { STAGE_OPTIONS, type Stage } from "../logic/label-columns";
import type { ExecMode } from "../logic/preview-summary";
import { DisabledReason } from "./disabled-reason";
import styles from "../labeling-page.module.css";

interface LabelToolbarProps {
  stage: Stage;
  onStageChange: (stage: Stage) => void;
  selectedCount: number;
  busy: boolean;
  onPreview: (mode: ExecMode) => void;
  onPrint: () => void;
  printDisabled: boolean;
  printReason: string | null;
  printing: boolean;
  onShip: () => void;
  shipBusy: boolean;
}

/**
 * 阶段切换 + 这一阶段的操作（只露这一步能做的，主按钮在最前）：
 * 待打单 → 打单 / 打单并发货；待发货 → 发货 / 打印面单 / 作废面单。
 * 没有勾选 / 组件未启动时按钮禁用并保持可见，悬停说明原因；进行中的按钮只转圈（ui-guidelines 第 7 节）。
 */
export function LabelToolbar({
  stage,
  onStageChange,
  selectedCount,
  busy,
  onPreview,
  onPrint,
  printDisabled,
  printReason,
  printing,
  onShip,
  shipBusy,
}: LabelToolbarProps) {
  const unpicked = selectedCount === 0 ? "先勾选订单" : null;
  const blocked = unpicked ?? (busy ? "有操作进行中" : null);
  return (
    <div className={styles.toolbar}>
      <SegmentedControl
        options={STAGE_OPTIONS}
        value={stage}
        onValueChange={(value) => onStageChange(value as Stage)}
        label="打单发货阶段"
      />
      <div className={styles.toolbarActions}>
        {selectedCount > 0 && <span className={styles.muted}>已选 {selectedCount} 单</span>}
        {stage === "pending" ? (
          <>
            <DisabledReason reason={unpicked}>
              <Button onClick={() => onPreview("obtain")} disabled={unpicked !== null} loading={busy}>
                打单
              </Button>
            </DisabledReason>
            <DisabledReason reason={blocked}>
              <Button variant="secondary" onClick={() => onPreview("fetch_and_ship")} disabled={blocked !== null}>
                打单并发货
              </Button>
            </DisabledReason>
          </>
        ) : (
          <>
            <DisabledReason reason={blocked}>
              <Button onClick={onShip} disabled={blocked !== null} loading={shipBusy}>
                发货
              </Button>
            </DisabledReason>
            <DisabledReason reason={printDisabled ? printReason : null}>
              <Button variant="secondary" onClick={onPrint} disabled={printDisabled} loading={printing}>
                打印面单
              </Button>
            </DisabledReason>
            <DisabledReason reason={blocked}>
              <Button variant="secondary" onClick={() => onPreview("void")} disabled={blocked !== null}>
                作废面单
              </Button>
            </DisabledReason>
          </>
        )}
      </div>
    </div>
  );
}

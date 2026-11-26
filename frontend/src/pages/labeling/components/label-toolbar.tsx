import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Button } from "@/components/arc/button/button";
import { STAGE_OPTIONS, type Stage } from "../logic/label-columns";
import type { ExecMode } from "../logic/preview-summary";
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
 * 没有勾选 / 组件未启动时按钮禁用并保持可见（ui-guidelines 第 7 节）。
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
  const none = selectedCount === 0 || busy;
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
            <Button onClick={() => onPreview("obtain")} disabled={none} loading={busy}>
              打单
            </Button>
            <Button variant="secondary" onClick={() => onPreview("fetch_and_ship")} disabled={none}>
              打单并发货
            </Button>
          </>
        ) : (
          <>
            <Button onClick={onShip} disabled={selectedCount === 0 || shipBusy || busy} loading={shipBusy}>
              发货
            </Button>
            <Button
              variant="secondary"
              onClick={onPrint}
              disabled={printDisabled}
              loading={printing}
              title={printReason ?? undefined}
            >
              打印面单
            </Button>
            <Button variant="secondary" onClick={() => onPreview("void")} disabled={none}>
              作废面单
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

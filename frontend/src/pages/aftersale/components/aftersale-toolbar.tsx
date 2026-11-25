import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { Select } from "@/components/arc/select/select";
import { SyncButton } from "@/components/custom/sync-control/sync-control";
import { VIEW_OPTIONS, isView, type AftersaleStatusOption, type View } from "../logic/aftersale-page";
import styles from "../aftersale-page.module.css";

interface ToolbarProps {
  view: View;
  onViewChange: (view: View) => void;
  status: number | undefined;
  onStatusChange: (status: number | undefined) => void;
  statusOptions: AftersaleStatusOption[];
  syncPending: boolean;
  onSync: () => void;
}

/** 视图切换 + 状态筛选 + 同步。状态选项来自平台报文文案（数字枚举取值未公开）。 */
export function AftersaleToolbar(props: ToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.filters}>
        <SegmentedControl
          label="售后视图"
          options={[...VIEW_OPTIONS]}
          value={props.view}
          onValueChange={(value) => {
            if (isView(value)) props.onViewChange(value);
          }}
        />
        {props.view === "all" && (
          <Select
            className={styles.filter}
            label="售后状态"
            value={props.status === undefined ? "all" : String(props.status)}
            onValueChange={(value) =>
              props.onStatusChange(value === "all" ? undefined : Number(value))
            }
            options={[
              { value: "all", label: "全部状态" },
              ...props.statusOptions.map((s) => ({ value: String(s.status), label: s.label })),
            ]}
          />
        )}
      </div>
      <SyncButton pending={props.syncPending} label="同步售后" onClick={props.onSync} />
    </div>
  );
}

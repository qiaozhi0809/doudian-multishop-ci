import SegmentedControl from "@/components/arc/segmented-control/segmented-control";
import { SyncButton } from "@/components/custom/sync-control/sync-control";
import { BILL_DAY_OPTIONS, FUND_TABS, isFundTab, type FundTab } from "../logic/fund-page";
import styles from "../fund-page.module.css";

interface ToolbarProps {
  tab: FundTab;
  onTabChange: (tab: FundTab) => void;
  days: number;
  onDaysChange: (days: number) => void;
  syncPending: boolean;
  onSync: () => void;
}

/** 标签页（待结算 / 保证金 / 账单）+ 账单时间范围 + 同步。 */
export function FundToolbar(props: ToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.filters}>
        <SegmentedControl
          label="资金视图"
          options={[...FUND_TABS]}
          value={props.tab}
          onValueChange={(value) => {
            if (isFundTab(value)) props.onTabChange(value);
          }}
        />
        {props.tab === "bills" && (
          <SegmentedControl
            label="账单时间范围"
            options={[...BILL_DAY_OPTIONS]}
            value={String(props.days)}
            onValueChange={(value) => props.onDaysChange(Number(value))}
          />
        )}
      </div>
      <SyncButton pending={props.syncPending} label="同步资金" onClick={props.onSync} />
    </div>
  );
}

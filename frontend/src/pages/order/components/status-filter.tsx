import { Select } from "@/components/arc/select/select";
import { LOCAL_STATUS_OPTIONS, isLocalStatus, type LocalStatus } from "../logic/order-columns";
import styles from "../order-page.module.css";

const ALL = "all";

/** 本地状态筛选（对应 GET /api/orders?status=），与平台口径的计数无关。 */
export function StatusFilter({ value, onChange }: { value: LocalStatus | undefined; onChange: (s: LocalStatus | undefined) => void }) {
  return (
    <Select
      className={styles.filter}
      label="本地状态"
      value={value ?? ALL}
      onValueChange={(v) => onChange(isLocalStatus(v) ? v : undefined)}
      options={[{ value: ALL, label: "全部状态" }, ...LOCAL_STATUS_OPTIONS]}
    />
  );
}

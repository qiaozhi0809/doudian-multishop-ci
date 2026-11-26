import { Alert } from "@/components/arc/alert/alert";
import { Select } from "@/components/arc/select/select";
import { usePoolItems } from "@/lib/use-pool-items";
import { availablePoolItems, poolOptionLabel } from "./available-pool";
import styles from "./pool-select.module.css";

interface PoolSelectProps {
  value: number | null;
  onChange: (id: number) => void;
  error?: string;
}

/** 从代理池里选一个可用代理（未被占用、未过期）。与代理池页共用同一份查询缓存。 */
export function PoolSelect({ value, onChange, error }: PoolSelectProps) {
  const pool = usePoolItems();
  const available = availablePoolItems(pool.data ?? []);

  if (pool.isError) return <Alert tone="danger" title="读取代理池失败，请稍后重试" />;
  const fieldError = error && (
    <span className={styles.error} role="alert">
      {error}
    </span>
  );

  if (pool.isSuccess && available.length === 0) {
    return (
      <div className={styles.field}>
        <Alert tone="info" title="池里没有可用代理" />
        {fieldError}
      </div>
    );
  }

  return (
    <div className={styles.field}>
      <Select
        label="池里的代理"
        placeholder={pool.isPending ? "读取中" : "请选择"}
        disabled={pool.isPending}
        value={value === null ? "" : String(value)}
        onValueChange={(v) => onChange(Number(v))}
        options={available.map((i) => ({ value: String(i.id), label: poolOptionLabel(i) }))}
      />
      {fieldError}
    </div>
  );
}

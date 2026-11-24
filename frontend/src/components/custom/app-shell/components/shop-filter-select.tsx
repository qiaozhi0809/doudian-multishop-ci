import { MultiSelect } from "@/components/arc/multi-select/multi-select";
import type { ShopRow } from "@/lib/use-shops";
import styles from "../app-shell.module.css";

interface ShopFilterSelectProps {
  shops: ShopRow[];
  shopIds: number[];
  disabled: boolean;
  onChange: (ids: number[]) => void;
}

/** 全局店铺筛选（多选，空 = 全部店铺）。 */
export function ShopFilterSelect({ shops, shopIds, disabled, onChange }: ShopFilterSelectProps) {
  const known = new Set(shops.map((s) => s.id));
  return (
    <MultiSelect
      className={styles.filter}
      label="店铺筛选"
      placeholder="全部店铺"
      disabled={disabled}
      options={shops.map((s) => ({ value: String(s.id), label: s.name }))}
      value={shopIds.filter((id) => known.has(id)).map(String)}
      onValueChange={(values) => onChange(values.map(Number))}
    />
  );
}

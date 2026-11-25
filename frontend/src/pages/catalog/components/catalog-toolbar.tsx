import { Input } from "@/components/arc/input/input";
import { SyncButton } from "@/components/custom/sync-control/sync-control";
import styles from "../catalog-page.module.css";

interface ToolbarProps {
  keyword: string;
  onKeywordChange: (value: string) => void;
  syncPending: boolean;
  onSync: () => void;
}

/** 关键字搜索 + 同步。商品状态的筛选值以平台为准，不自造 tab 枚举。 */
export function CatalogToolbar({ keyword, onKeywordChange, syncPending, onSync }: ToolbarProps) {
  return (
    <div className={styles.toolbar}>
      <Input
        className={styles.filter}
        label="搜索商品"
        placeholder="商品名称关键字"
        value={keyword}
        onChange={(event) => onKeywordChange(event.target.value)}
      />
      <SyncButton pending={syncPending} label="同步商品" onClick={onSync} />
    </div>
  );
}

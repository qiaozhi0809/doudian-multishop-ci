import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { withoutShops } from "@/lib/open-problem-shops";
import styles from "./shop-failure-alert.module.css";

export interface ShopFailure {
  shopId: number;
  error: string | null;
}

export interface ShopFailureAlertProps {
  /** 没取到数据的店；同一家店出现多次（多个来源）只算一次。 */
  failures: ShopFailure[];
  shopName: (id: number) => string;
  /** 顶部横条里已列出的店（useShopsWithOpenProblems）：不在这里重复。 */
  bannerShopIds?: ReadonlySet<number>;
  className?: string;
}

const NONE: ReadonlySet<number> = new Set();

/** 部分店铺失败（全站共用）：「N 家店未取到」，展开看是哪几家及原因；没有要列的店时整条不显示。 */
export function ShopFailureAlert({ failures, shopName, bannerShopIds = NONE, className }: ShopFailureAlertProps) {
  const [expanded, setExpanded] = useState(false);
  const byShop = new Map<number, ShopFailure>();
  for (const failure of withoutShops(failures, bannerShopIds)) {
    if (!byShop.has(failure.shopId)) byShop.set(failure.shopId, failure);
  }
  if (byShop.size === 0) return null;
  return (
    <Alert tone="warning" title={`${byShop.size} 家店未取到`} className={className}>
      <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
        {expanded ? "收起原因" : "查看原因"}
      </Button>
      {/* Alert 把内容放在 <p> 里，列表只能用 span 搭 */}
      {expanded && (
        <span className={styles.list} role="list">
          {[...byShop.values()].map((failure) => (
            <span key={failure.shopId} className={styles.item} role="listitem">
              {shopName(failure.shopId)}：{failure.error ?? "原因未知，请稍后重试"}
            </span>
          ))}
        </span>
      )}
    </Alert>
  );
}

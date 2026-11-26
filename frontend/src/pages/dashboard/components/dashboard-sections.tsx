import { useState } from "react";
import { Alert } from "@/components/arc/alert/alert";
import { Button } from "@/components/arc/button/button";
import { withoutShops } from "@/lib/open-problem-shops";
import type { SourceFailure } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

/** 部分店铺上游失败：不让整页报错，提示「N 家店未取到」并可展开看原因；已在顶部横条的店不重复。 */
export function SourceFailures({
  failures,
  shopName,
  bannerShopIds,
}: {
  failures: SourceFailure[];
  shopName: (id: number) => string;
  bannerShopIds: ReadonlySet<number>;
}) {
  const [expanded, setExpanded] = useState(false);
  const unique = withoutShops([...new Map(failures.map((failure) => [failure.shopId, failure])).values()], bannerShopIds);
  if (unique.length === 0) return null;
  return (
    <Alert tone="warning" title={`${unique.length} 家店未取到`}>
      <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
        {expanded ? "收起原因" : "查看原因"}
      </Button>
      {expanded && (
        // Alert 的内容包在段落里，列表用 span 搭，避免段落里套 ul
        <span role="list" className={styles.failList}>
          {unique.map((failure) => (
            <span role="listitem" key={failure.shopId}>
              {shopName(failure.shopId)}：{failure.error ?? "原因未知，请稍后重试"}
            </span>
          ))}
        </span>
      )}
    </Alert>
  );
}

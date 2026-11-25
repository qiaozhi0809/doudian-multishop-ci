import { Alert } from "@/components/arc/alert/alert";
import type { SourceFailure } from "../logic/dashboard";
import styles from "../dashboard-page.module.css";

/** 部分店铺上游失败：不让整页报错，提示合计不含这些店并列出原因。 */
export function SourceFailures({
  failures,
  shopName,
}: {
  failures: SourceFailure[];
  shopName: (id: number) => string;
}) {
  const unique = [...new Map(failures.map((failure) => [failure.shopId, failure])).values()];
  if (unique.length === 0) return null;
  return (
    <section className={styles.failureBlock}>
      <Alert tone="warning" title={`${unique.length} 家店未取到部分平台数据，合计不含这些店`} />
      <ul className={styles.failList}>
        {unique.map((failure) => (
          <li key={failure.shopId}>
            {shopName(failure.shopId)}：{failure.error ?? "原因未知，请稍后重试"}
          </li>
        ))}
      </ul>
    </section>
  );
}

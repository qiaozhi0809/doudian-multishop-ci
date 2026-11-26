import { Fragment } from "react";
import type { BannerRow } from "../logic/notification-view";
import styles from "../notification-center.module.css";

/** 「店A：登录失效、出口不通」，每个问题单独可点，跳各自的链接。 */
export function ProblemLinks({ row, onNavigate }: { row: BannerRow; onNavigate: (link: string) => void }) {
  return (
    <span className={styles.itemTitle}>
      {row.shopName}：
      {row.problems.map((problem, i) => (
        <Fragment key={problem.kind}>
          {i > 0 && "、"}
          <button type="button" className={styles.problemLink} onClick={() => onNavigate(problem.link)}>
            {problem.label}
          </button>
        </Fragment>
      ))}
    </span>
  );
}

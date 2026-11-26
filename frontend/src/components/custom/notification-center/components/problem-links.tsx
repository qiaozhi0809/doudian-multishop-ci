import { Fragment } from "react";
import { ChevronRight } from "lucide-react";
import type { BannerRow } from "../logic/notification-view";
import styles from "../notification-center.module.css";

/** 「店A [登录失效 ›] [出口不通 ›]」，每个问题是一个可点的胶囊，跳各自的链接。冒号与顿号只给读屏。 */
export function ProblemLinks({ row, onNavigate }: { row: BannerRow; onNavigate: (link: string) => void }) {
  return (
    <span className={styles.problems}>
      <span className={styles.problemShop}>
        {row.shopName}
        <span className={styles.srOnly}>：</span>
      </span>
      {row.problems.map((problem, i) => (
        <Fragment key={problem.kind}>
          {i > 0 && <span className={styles.srOnly}>、</span>}
          <button type="button" className={styles.problemLink} onClick={() => onNavigate(problem.link)}>
            {problem.label}
            <ChevronRight size={14} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </Fragment>
      ))}
    </span>
  );
}

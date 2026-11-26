import type { ReactElement } from "react";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import styles from "../labeling-page.module.css";

/** 禁用按钮的原因提示：禁用元素收不到悬停和焦点，外包一层可聚焦的 span（ui-guidelines 第 7 节）。 */
export function DisabledReason({ reason, children }: { reason: string | null; children: ReactElement }) {
  if (reason === null) return children;
  return (
    <Tooltip content={reason}>
      <span className={styles.tip} tabIndex={0}>
        {children}
      </span>
    </Tooltip>
  );
}

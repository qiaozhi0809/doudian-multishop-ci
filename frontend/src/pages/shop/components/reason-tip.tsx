import type { ReactNode } from "react";
import { Tooltip } from "@/components/arc/tooltip/tooltip";
import styles from "../shop-page.module.css";

/** 禁用控件的原因：外层可聚焦的 span 挂提示气泡（禁用的按钮收不到焦点）；没有原因时原样返回。 */
export function ReasonTip({ reason, children }: { reason: string | null; children: ReactNode }) {
  if (!reason) return <>{children}</>;
  return (
    <Tooltip content={reason}>
      <span className={styles.tip} tabIndex={0}>
        {children}
      </span>
    </Tooltip>
  );
}

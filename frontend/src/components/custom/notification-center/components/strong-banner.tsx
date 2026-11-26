import { ChevronRight, CircleX } from "lucide-react";
import type { BannerView } from "../logic/notification-view";
import styles from "../notification-center.module.css";
import { ProblemLinks } from "./problem-links";

interface StrongBannerProps {
  view: BannerView;
  onNavigate: (link: string) => void;
  onOpenPanel: () => void;
}

/** 与 Arc Alert 的 danger 同一图标与大小 */
const icon = <CircleX className={styles.bannerIcon} size={18} strokeWidth={1.75} aria-hidden="true" />;

/** 全站顶部红色横条：未解决的强提醒一店一行（每个问题跳各自的链接），超过 3 家合并；问题恢复才消失，不能手动关。 */
export function StrongBanner({ view, onNavigate, onOpenPanel }: StrongBannerProps) {
  if (view.kind === "none") return null;
  return (
    <section className={styles.banner} aria-label="需要处理的店铺">
      {view.kind === "merged" ? (
        <button type="button" className={styles.bannerRow} onClick={onOpenPanel}>
          {icon}
          <span className={styles.problemShop}>{view.text}</span>
          <ChevronRight className={styles.bannerMore} size={16} strokeWidth={1.75} aria-hidden="true" />
        </button>
      ) : (
        view.rows.map((row) => (
          <div key={row.shopId} role="group" aria-label={row.shopName} className={styles.bannerRow} data-static>
            {icon}
            <ProblemLinks row={row} onNavigate={onNavigate} />
          </div>
        ))
      )}
    </section>
  );
}

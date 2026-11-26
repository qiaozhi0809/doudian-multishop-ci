import { CircleAlert } from "lucide-react";
import type { BannerView } from "../logic/notification-view";
import styles from "../notification-center.module.css";

interface StrongBannerProps {
  view: BannerView;
  onNavigate: (link: string) => void;
  onOpenPanel: () => void;
}

/** 全站顶部红色横条：未解决的强提醒一店一行，超过 3 家合并；问题恢复才消失，不能手动关。 */
export function StrongBanner({ view, onNavigate, onOpenPanel }: StrongBannerProps) {
  if (view.kind === "none") return null;
  const rows =
    view.kind === "merged"
      ? [{ key: "merged", text: view.text, onClick: onOpenPanel }]
      : view.rows.map((row) => ({ key: String(row.shopId), text: row.text, onClick: () => onNavigate(row.link) }));
  return (
    <section className={styles.banner} aria-label="需要处理的店铺">
      {rows.map((row) => (
        <button key={row.key} type="button" className={styles.bannerRow} onClick={row.onClick}>
          <CircleAlert className={styles.bannerIcon} size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{row.text}</span>
        </button>
      ))}
    </section>
  );
}

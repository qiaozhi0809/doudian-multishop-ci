import type { ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "motion/react";
import { Store } from "lucide-react";
import { motionTokens } from "@/components/arc/motion-tokens";
import { useViewHeight } from "../hooks/use-view-height";
import styles from "../auth-page.module.css";

/** 视图从小的模糊里升上来；减少动态效果时只淡入淡出。 */
const stepMotion: Variants = {
  enter: (reduce: boolean) =>
    reduce ? { opacity: 0 } : { opacity: 0, y: 12, filter: `blur(${motionTokens.blur.soft}px)` },
  center: (reduce: boolean) => ({
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: reduce
      ? { duration: motionTokens.duration.instant }
      : { duration: motionTokens.duration.standard, ease: [...motionTokens.ease.enter] },
  }),
  exit: (reduce: boolean) =>
    reduce
      ? { opacity: 0, transition: { duration: 0 } }
      : {
          opacity: 0,
          y: -8,
          filter: `blur(${motionTokens.blur.soft}px)`,
          transition: { duration: motionTokens.duration.exit, ease: [...motionTokens.ease.standard] },
        },
};

interface AuthLayoutProps {
  /** 当前视图（loading / error / login / setup / done）；变化时卡片高度按弹簧过渡、内容换场。 */
  view: string;
  aside?: ReactNode;
  children: ReactNode;
}

/** 左右分栏：左边品牌与表单卡片，右边深色内容区（窄窗口收起）。不传 aside 时单栏居中（路由守卫的加载 / 出错）。 */
export function AuthLayout({ view, aside, children }: AuthLayoutProps) {
  const reduce = !!useReducedMotion();
  const { track, height } = useViewHeight(view, reduce);
  return (
    <div className={aside ? styles.screen : `${styles.screen} ${styles.solo}`}>
      <main className={styles.pane}>
        <header className={styles.bar}>
          <span className={styles.brand}>
            <span className={styles.mark} aria-hidden="true">
              <Store size={16} strokeWidth={1.75} />
            </span>
            抖店管理
          </span>
        </header>
        <div className={styles.stage}>
          <motion.div className={styles.viewport} style={{ height }}>
            <div ref={track} className={styles.track}>
              <AnimatePresence mode="popLayout" initial={false} custom={reduce}>
                <motion.div
                  key={view}
                  className={styles.step}
                  custom={reduce}
                  variants={stepMotion}
                  initial="enter"
                  animate="center"
                  exit="exit"
                >
                  {children}
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </main>
      {aside ? (
        <aside className={styles.aside} aria-label="产品介绍">
          {aside}
        </aside>
      ) : null}
    </div>
  );
}

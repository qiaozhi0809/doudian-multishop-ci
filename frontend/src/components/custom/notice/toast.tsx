import { motion, useIsPresent, useReducedMotion, type Transition } from "motion/react";
import { Check, CircleX, Info, MessageSquare, ShoppingBag, TriangleAlert, Undo2, X, type LucideIcon } from "lucide-react";
import { motionTokens } from "@/components/arc/lib/motion-tokens";
import type { NoticeEvent, NoticeTone } from "./notice-types";
import styles from "./notice.module.css";

export interface ToastItem {
  id: number;
  key: string;
  text: string;
  body?: string;
  tone: NoticeTone;
  event?: NoticeEvent;
  persistent: boolean;
}

/** 状态图标与 Arc Alert 一致 */
const TONE_ICONS: Record<NoticeTone, LucideIcon> = { success: Check, info: Info, warning: TriangleAlert, danger: CircleX };
/** 事件弹窗按种类换图标；其他通知沿用状态图标 */
const EVENT_ICONS: Record<NoticeEvent, LucideIcon | null> = { order: ShoppingBag, aftersale: Undo2, message: MessageSquare, system: null };

const fade: Transition = { duration: motionTokens.duration.instant };
const leave: Transition = { duration: motionTokens.duration.fast, ease: [...motionTokens.ease.standard] };

interface ToastProps {
  item: ToastItem;
  onDismiss: () => void;
  onPause: () => void;
  onResume: () => void;
}

/** 一条浮动提示：进场上移淡入，离场右移淡出，其余提示平滑补位；减少动态效果时只淡入淡出。 */
export function Toast({ item, onDismiss, onPause, onResume }: ToastProps) {
  const reduced = useReducedMotion();
  // 离场中的那条不再被读屏读到、也不再响应点击
  const present = useIsPresent();
  const Icon = (item.event && EVENT_ICONS[item.event]) || TONE_ICONS[item.tone];
  return (
    <motion.div
      layout={reduced ? false : "position"}
      className={styles.toast}
      data-tone={item.tone}
      data-event={item.event}
      data-leaving={present ? undefined : true}
      role={item.tone === "danger" ? "alert" : "status"}
      aria-hidden={present ? undefined : true}
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={reduced ? { opacity: 0, transition: fade } : { opacity: 0, x: 16, transition: leave }}
      transition={reduced ? fade : motionTokens.spring.smooth}
      onMouseEnter={onPause}
      onMouseLeave={onResume}
    >
      <Icon className={styles.icon} size={18} strokeWidth={1.75} aria-hidden="true" />
      <span className={styles.copy}>
        <span className={styles.title}>{item.text}</span>
        {item.body && <span className={styles.body}>{item.body}</span>}
      </span>
      <button type="button" className={styles.close} aria-label="关闭提示" onClick={onDismiss}>
        <X size={16} strokeWidth={1.75} aria-hidden="true" />
      </button>
    </motion.div>
  );
}

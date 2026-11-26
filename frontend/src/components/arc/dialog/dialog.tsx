"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { createContext, useCallback, useContext, useLayoutEffect, useRef, useState } from "react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Transition } from "motion/react";
import { X } from "lucide-react";
import { motionTokens } from "../lib/motion-tokens";
import styles from "./dialog.module.css";

/** Mirrors the open state so the content can stay mounted while it animates out, and retarget mid-flight if it is reopened or closed early. */
const OpenContext = createContext<boolean | null>(null);

/** busy（本项目加的）：请求进行中不能关闭（取消、Esc、点遮罩、× 都不生效），免得失败结果在对话框关掉后被静默丢掉。 */
export function Dialog({ open: openProp, defaultOpen = false, onOpenChange, busy = false, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Root> & { busy?: boolean }) {
  const [uncontrolled, setUncontrolled] = useState(defaultOpen);
  const open = openProp ?? uncontrolled;
  const setOpen = useCallback((next: boolean) => { if (!next && busy) return; if (openProp === undefined) setUncontrolled(next); onOpenChange?.(next); }, [openProp, onOpenChange, busy]);
  return <OpenContext.Provider value={open}><DialogPrimitive.Root {...props} open={open} onOpenChange={setOpen}/></OpenContext.Provider>;
}

export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export interface DialogContentProps extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  title: string;
  description?: string;
  children: ReactNode;
  /** confirm: 确认框形态，无头部分隔线与 ×，标题、说明、按钮成一个整块。 */
  variant?: "default" | "confirm";
}

const fade: Transition = { duration: motionTokens.duration.instant };
const leave: Transition = { duration: motionTokens.duration.fast, ease: [...motionTokens.ease.standard] };

/** When the title or description changes while open, the new copy rises in and the old copy leaves upward. */
function SwapText({ text }: { text: string }) {
  const reduced = useReducedMotion();
  return <AnimatePresence mode="popLayout" initial={false}>
    <motion.span key={text} className={styles.swap} initial={reduced ? false : { opacity: 0, y: "0.3em", filter: `blur(${motionTokens.blur.soft}px)` }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, y: "-0.3em", filter: `blur(${motionTokens.blur.subtle}px)`, transition: { duration: motionTokens.duration.fast, ease: [...motionTokens.ease.standard] } }} transition={{ duration: motionTokens.duration.standard, ease: [...motionTokens.ease.enter] }}>{text}</motion.span>
  </AnimatePresence>;
}

export function DialogContent({ title, description, children, className, variant = "default", onPointerDownOutside, onOpenAutoFocus, ...props }: DialogContentProps) {
  const open = useContext(OpenContext);
  const reduced = useReducedMotion();
  // When the open state last changed. Radix waits for the click before treating a press as outside, and a press on the trigger
  // while the dialog leaves reopens it first, so that press must not close it again.
  const change = useRef({ open, at: 0 });
  useLayoutEffect(() => { change.current = { open, at: performance.now() }; }, [open]);
  const pressOutside: DialogContentProps["onPointerDownOutside"] = event => {
    onPointerDownOutside?.(event);
    if (open !== null && (!change.current.open || event.detail.originalEvent.timeStamp < change.current.at)) event.preventDefault();
  };
  const confirm = variant === "confirm";
  // 确认框打开时不把焦点自动给「取消」：脚本聚焦在某些情况下会被当成键盘聚焦，画出黑色焦点框。
  // 改为聚焦弹窗本身（无框），键盘用户按 Tab 仍会到按钮上，那时才显示焦点框。
  const autoFocus: DialogContentProps["onOpenAutoFocus"] = event => {
    onOpenAutoFocus?.(event);
    if (!confirm || event.defaultPrevented) return;
    event.preventDefault();
    (event.currentTarget as HTMLElement | null ?? event.target as HTMLElement | null)?.focus?.({ preventScroll: true });
  };
  const classes = [styles.content, confirm ? styles.confirm : "", className].filter(Boolean).join(" ");
  const inner = <>
    <div className={styles.header}><div><DialogPrimitive.Title className={styles.title}><SwapText text={title}/></DialogPrimitive.Title>{description ? <DialogPrimitive.Description className={styles.description}><SwapText text={description}/></DialogPrimitive.Description> : null}</div>{confirm ? null : <DialogPrimitive.Close className={styles.close} aria-label="关闭"><X size={16} strokeWidth={1.75} aria-hidden="true"/></DialogPrimitive.Close>}</div>
    <div className={styles.body}>{children}</div>
  </>;
  // Under a bare Radix root the open state is unknown here, so CSS keyframes keyed off data-state animate the layers instead.
  if (open === null) return <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className={`${styles.overlay} ${styles.keyframes}`}/>
    <DialogPrimitive.Content {...props} onOpenAutoFocus={autoFocus} onPointerDownOutside={pressOutside} className={`${classes} ${styles.keyframes}`}>{inner}</DialogPrimitive.Content>
  </DialogPrimitive.Portal>;
  // The overlay fades while the dialog rises 8px and scales up on a spring. Closing is shorter and quieter, and starts from wherever the entrance is.
  return <AnimatePresence>
    {open && <DialogPrimitive.Portal key="dialog" forceMount>
      <DialogPrimitive.Overlay asChild forceMount><motion.div className={styles.overlay} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: reduced ? fade : leave }} transition={reduced ? fade : { duration: motionTokens.duration.standard, ease: [...motionTokens.ease.enter] }}/></DialogPrimitive.Overlay>
      <DialogPrimitive.Content {...props} onOpenAutoFocus={autoFocus} onPointerDownOutside={pressOutside} asChild forceMount>
        <motion.div className={classes} initial={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: .96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={reduced ? { opacity: 0, transition: fade } : { opacity: 0, y: 4, scale: .98, transition: leave }} transition={reduced ? fade : { default: motionTokens.spring.smooth, opacity: { duration: motionTokens.duration.fast, ease: [...motionTokens.ease.enter] } }}>{inner}</motion.div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>}
  </AnimatePresence>;
}

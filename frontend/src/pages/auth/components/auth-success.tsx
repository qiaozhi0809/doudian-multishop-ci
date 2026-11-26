import { useEffect, useRef } from "react";
import { motion, useReducedMotion, type Transition } from "motion/react";
import { motionTokens } from "@/components/arc/motion-tokens";
import styles from "../auth-page.module.css";

/** 成功后的过渡：先画圆再画对勾，标题获得焦点并播报，随后由页面跳转。 */
export function AuthSuccess({ title }: { title: string }) {
  const reduce = !!useReducedMotion();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  const draw = (delay: number, duration: number) => {
    const transition: Transition = {
      pathLength: { duration, ease: [...motionTokens.ease.inOut], delay },
      opacity: { duration: motionTokens.duration.instant, delay },
    };
    return { initial: reduce ? false : { pathLength: 0, opacity: 0 }, animate: { pathLength: 1, opacity: 1 }, transition };
  };
  return (
    <div role="status">
      <svg className={styles.success} viewBox="0 0 48 48" aria-hidden="true">
        <g transform="rotate(-90 24 24)">
          <motion.circle
            cx="24"
            cy="24"
            r="22.25"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            {...draw(0.12, motionTokens.duration.considered)}
          />
        </g>
        <motion.path
          d="M15.5 24.5l5.5 5.5 11.5-12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          {...draw(0.4, motionTokens.duration.standard + 0.08)}
        />
      </svg>
      <div className={styles.heading}>
        <h1 ref={heading} tabIndex={-1}>
          {title}
        </h1>
        <p>正在进入</p>
      </div>
    </div>
  );
}

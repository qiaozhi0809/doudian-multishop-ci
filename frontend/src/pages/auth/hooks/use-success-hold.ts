import { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

/** 完成动画的停留时间：对勾画完再跳转；减少动态效果时只留一下。 */
export const SUCCESS_HOLD_MS = 1000;
export const SUCCESS_HOLD_REDUCED_MS = 300;

/**
 * 登录 / 创建成功后先播完成动画再跳转。
 * 提交时就先挡住跳转（成功后状态刷新会立刻算出跳转目标），失败时放开。
 */
export function useSuccessHold() {
  const reduce = !!useReducedMotion();
  const [holding, setHolding] = useState(false);
  const [done, setDone] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const run = useCallback(
    async (action: () => Promise<boolean>) => {
      setHolding(true);
      const ok = await action();
      if (!ok) {
        setHolding(false);
        return;
      }
      setDone(true);
      timer.current = window.setTimeout(() => setHolding(false), reduce ? SUCCESS_HOLD_REDUCED_MS : SUCCESS_HOLD_MS);
    },
    [reduce],
  );

  return { holding, done, run };
}

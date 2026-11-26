import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { animate, useMotionValue } from "motion/react";
import { motionTokens } from "@/components/arc/motion-tokens";

/**
 * 卡片高度只在视图切换（加载 → 表单 → 完成）时按弹簧过渡，平时保持 auto，字段提示即时展开。
 * 参考壹帆智播 login-centered 的同名做法。
 */
export function useViewHeight(view: string, reduce: boolean) {
  const track = useRef<HTMLDivElement>(null);
  const height = useMotionValue<number | "auto">("auto");
  const measured = useRef(0);
  const gliding = useRef(false);
  const lastView = useRef(view);

  const glide = useCallback(
    (to: number) => {
      gliding.current = true;
      animate(height, to, {
        ...motionTokens.spring.smooth,
        onComplete: () => {
          gliding.current = false;
          height.jump("auto");
        },
      });
    },
    [height],
  );

  useEffect(() => {
    const node = track.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      measured.current = entry.borderBoxSize?.[0]?.blockSize ?? node.offsetHeight;
      if (gliding.current) glide(measured.current);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [glide]);

  useLayoutEffect(() => {
    if (lastView.current === view) return;
    lastView.current = view;
    const current = height.get();
    const from = typeof current === "number" ? current : measured.current;
    const to = track.current?.offsetHeight ?? 0;
    if (reduce || !from || !to) {
      gliding.current = false;
      height.jump("auto");
      return;
    }
    if (current === "auto") height.jump(from);
    glide(to);
  }, [view, reduce, height, glide]);

  return { track, height };
}

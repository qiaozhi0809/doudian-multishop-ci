import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { AnimatePresence } from "motion/react";
import { NOTICE_ROOT } from "./keep-open-on-notice";
import type { NoticeEvent, NoticeTone } from "./notice-types";
import styles from "./notice.module.css";
import { Toast, type ToastItem } from "./toast";

export type { NoticeEvent, NoticeTone };
export interface NoticeOptions {
  /** 同一个 key 的提示互相替换（如某店的「等待扫码」被「登录成功」取代）；不给则按文字去重。 */
  key?: string;
  /** 停留时长（毫秒）；不给时普通 4 秒、报错 8 秒。 */
  holdMs?: number;
  /** 常驻：不自动消失、换页面也不收起，只能手动关闭（强提醒用）。 */
  persistent?: boolean;
  /** 标题下的第二行（原因、明细）。 */
  body?: string;
  /** 事件弹窗（新订单、新售后、新消息等）：与操作结果提示视觉区分。 */
  event?: NoticeEvent;
}
export type Notify = (text: string, tone?: NoticeTone, options?: NoticeOptions) => void;

/** 没有 Provider 时为 null：调用方据此退回页面内提示（单独渲染页面的测试里会这样）。 */
const NoticeContext = createContext<Notify | null>(null);

const HOLD_MS = 4000;
/** 报错多留一会儿，让人读完 */
const HOLD_DANGER_MS = 8000;
/** 普通提示最多同时显示几条；常驻的强提醒不计入、也不会被挤掉。 */
const MAX_VISIBLE = 4;

function trim(list: ToastItem[]): ToastItem[] {
  const evict = list.filter((item) => !item.persistent).length - MAX_VISIBLE;
  if (evict <= 0) return list;
  const dropped = new Set(list.filter((item) => !item.persistent).slice(0, evict).map((item) => item.id));
  return list.filter((item) => !dropped.has(item.id));
}

interface Timer {
  handle: number;
  end: number;
  left: number;
}

/**
 * 右下角浮动提示（同壹帆智播 notice.tsx）：操作结果不再插在页面里把表格往下推。
 * 普通 4 秒、报错 8 秒自动消失（可用 holdMs 指定，persistent 常驻）；鼠标停在上面暂停计时；
 * 换页面收起上一页的提示（常驻的保留）；同 key 只留一条。
 * 需要用户处理才能继续的问题（读取失败、演练模式）仍用页面内提示条，不要靠这里。
 */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const timers = useRef(new Map<number, Timer>());
  const { pathname } = useLocation();

  const clear = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer) window.clearTimeout(timer.handle);
    timers.current.delete(id);
  }, []);

  const dismiss = useCallback(
    (id: number) => {
      clear(id);
      setItems((list) => list.filter((item) => item.id !== id));
    },
    [clear],
  );

  const start = useCallback(
    (id: number, ms: number) => {
      clear(id);
      timers.current.set(id, { handle: window.setTimeout(() => dismiss(id), ms), end: Date.now() + ms, left: ms });
    },
    [clear, dismiss],
  );

  const pause = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (!timer) return;
    window.clearTimeout(timer.handle);
    timer.left = Math.max(timer.end - Date.now(), 500);
  }, []);

  const resume = useCallback(
    (id: number) => {
      const timer = timers.current.get(id);
      if (timer) start(id, timer.left);
    },
    [start],
  );

  // 换页面就收起上一页的提示（渲染时比较路径；残留的计时器到点只会删掉已不存在的条目）
  const [shownPath, setShownPath] = useState(pathname);
  if (shownPath !== pathname) {
    setShownPath(pathname);
    setItems((list) => list.filter((item) => item.persistent));
  }

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) window.clearTimeout(timer.handle);
      pending.clear();
    };
  }, []);

  const notify = useCallback<Notify>(
    (text, tone = "success", options = {}) => {
      if (!text) return;
      seq.current += 1;
      const id = seq.current;
      const key = options.key ?? text;
      setItems((list) => {
        for (const old of list.filter((item) => item.key === key)) clear(old.id);
        const persistent = options.persistent === true;
        const next: ToastItem = { id, key, text, tone, persistent, body: options.body, event: options.event };
        // 同 key 原地替换内容（不先飞出再飞进），挪到最下面
        return trim([...list.filter((item) => item.key !== key), next]);
      });
      if (!options.persistent) start(id, options.holdMs ?? (tone === "danger" ? HOLD_DANGER_MS : HOLD_MS));
    },
    [clear, start],
  );

  return (
    <NoticeContext.Provider value={notify}>
      {children}
      <div className={styles.toasts} aria-label="操作提示" {...{ [NOTICE_ROOT]: true }}>
        <AnimatePresence>
          {items.map((item) => (
            <Toast
              key={item.key}
              item={item}
              onDismiss={() => dismiss(item.id)}
              onPause={() => pause(item.id)}
              onResume={() => resume(item.id)}
            />
          ))}
        </AnimatePresence>
      </div>
    </NoticeContext.Provider>
  );
}

/** 发右下角提示；不在 NoticeProvider 里时返回 null。 */
export const useNotice = () => useContext(NoticeContext);

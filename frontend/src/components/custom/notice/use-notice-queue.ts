import { useCallback, useRef, useState } from "react";
import type { NoticeTone } from "./notice-types";

export interface QueuedNotice {
  id: number;
  /** 同一个 key 的提示互相替换（如某店的「等待扫码」被「登录成功」取代、同一代理多次检查只留最新一条） */
  key: string;
  tone: NoticeTone;
  text: string;
}

/** 页面里的操作结果队列：交给 <NoticeList> 发到右下角浮动提示，同 key 只留一条。 */
export function useNoticeQueue() {
  const [notices, setNotices] = useState<QueuedNotice[]>([]);
  const nextId = useRef(1);
  const notify = useCallback((key: string, tone: NoticeTone, text: string) => {
    setNotices((prev) => [...prev.filter((n) => n.key !== key), { id: nextId.current++, key, tone, text }]);
  }, []);
  const dismissNotice = useCallback((id: number) => setNotices((prev) => prev.filter((n) => n.id !== id)), []);
  return { notices, notify, dismissNotice };
}

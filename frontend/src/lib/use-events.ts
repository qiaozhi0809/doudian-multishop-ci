import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./query-keys";

type Handler = (data: unknown) => void;

/** 全应用共用一个 EventSource：有订阅者时建立，最后一个订阅者退订后关闭。 */
const hub = {
  source: null as EventSource | null,
  handlers: new Map<string, Set<Handler>>(),
  attached: new Map<string, (e: Event) => void>(),
  count: 0,

  subscribe(name: string, handler: Handler): () => void {
    if (!hub.source) hub.source = new EventSource("/api/events");
    const source = hub.source;
    hub.count += 1;
    let set = hub.handlers.get(name);
    if (!set) {
      set = new Set();
      hub.handlers.set(name, set);
      const listener = (e: Event) => {
        let data: unknown = undefined;
        if (name !== "open") {
          try {
            data = JSON.parse((e as MessageEvent<string>).data);
          } catch {
            return; // 无法解析的事件数据直接忽略
          }
        }
        hub.handlers.get(name)?.forEach((h) => h(data));
      };
      hub.attached.set(name, listener);
      source.addEventListener(name, listener);
    }
    set.add(handler);

    return () => {
      set.delete(handler);
      hub.count -= 1;
      if (hub.count === 0) {
        hub.attached.forEach((listener, n) => source.removeEventListener(n, listener));
        hub.attached.clear();
        hub.handlers.clear();
        source.close();
        hub.source = null;
      }
    };
  },
};

/** 订阅单个 SSE 事件；handler 变化不会重建订阅，卸载时退订。`open` 表示连接建立（含重连）。 */
export function useEventSubscription<T = unknown>(name: string, handler: (data: T) => void): void {
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  });
  useEffect(() => hub.subscribe(name, (data) => latest.current(data as T)), [name]);
}

/** 应用级：SSE 事件让对应查询失效；连接建立（含断线重连）时全部失效，避免停留在旧状态。 */
export function useEvents(): void {
  const client = useQueryClient();
  useEventSubscription("shop_status_changed", () => {
    void client.invalidateQueries({ queryKey: queryKeys.shops() });
  });
  useEventSubscription("sync_progress", () => {
    void client.invalidateQueries({ queryKey: queryKeys.ordersRoot() });
    void client.invalidateQueries({ queryKey: queryKeys.orderCountsRoot() });
  });
  useEventSubscription("open", () => {
    void client.invalidateQueries();
  });
}

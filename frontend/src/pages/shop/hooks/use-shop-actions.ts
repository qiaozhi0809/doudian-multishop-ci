import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import type { ShopRow } from "@/lib/use-shops";
import { egressCheckResult } from "../logic/egress-check-result";

type Schemas = components["schemas"];
type EgressRequest = Schemas["EgressRequest"];

export interface Notice {
  id: number;
  /** 同一个 key 的通知会互相替换（如某店的「等待扫码」被「登录成功」取代） */
  key: string;
  tone: "info" | "success" | "warning" | "danger";
  text: string;
}

const LOGIN_WAIT_TIMEOUT_MS = 10 * 60 * 1000;
const FALLBACK_ERROR = "请求失败，请确认本地服务正常后重试";
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : FALLBACK_ERROR);

/** 店铺页的各项操作：结果以页面内通知呈现（不只靠 toast）；扫码登录有等待态与超时。 */
export function useShopActions(shops: ShopRow[]) {
  const client = useQueryClient();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [pending, setPending] = useState<string[]>([]);
  const [waitingShopIds, setWaiting] = useState<number[]>([]);
  const waitingRef = useRef<number[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const nextId = useRef(1);
  const shopsRef = useRef(shops);
  useEffect(() => {
    shopsRef.current = shops;
  });

  const nameOf = (id: number) => shopsRef.current.find((s) => s.id === id)?.name ?? `店铺 ${id}`;

  const notify = useCallback((key: string, tone: Notice["tone"], text: string) => {
    setNotices((prev) => [...prev.filter((n) => n.key !== key), { id: nextId.current++, key, tone, text }]);
  }, []);

  const dismissNotice = useCallback((id: number) => setNotices((prev) => prev.filter((n) => n.id !== id)), []);

  /** 刷新店铺；出口占用的池项也随之变化，一并刷新池。 */
  const refreshShops = () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.shops() }),
      client.invalidateQueries({ queryKey: queryKeys.proxyPool() }),
    ]);

  /** 记录进行中的操作，结束时移除；返回操作结果。 */
  const track = useCallback(async <T,>(key: string, fn: () => Promise<T>): Promise<T> => {
    setPending((p) => [...p, key]);
    try {
      return await fn();
    } finally {
      setPending((p) => p.filter((k) => k !== key));
    }
  }, []);

  const setWaitingIds = (ids: number[]) => {
    waitingRef.current = ids;
    setWaiting(ids);
  };
  const finishWaiting = (shopId: number) => {
    const timer = timers.current.get(shopId);
    if (timer) clearTimeout(timer);
    timers.current.delete(shopId);
    setWaitingIds(waitingRef.current.filter((id) => id !== shopId));
  };

  useEventSubscription<{ shop_id: number; status?: string }>("shop_status_changed", (d) => {
    if (d.status !== "active" || !waitingRef.current.includes(d.shop_id)) return;
    finishWaiting(d.shop_id);
    notify(`login:${d.shop_id}`, "success", `${nameOf(d.shop_id)}：扫码登录成功`);
  });
  useEventSubscription<{ shop_id: number; reason: string }>("shop_login_failed", (d) => {
    if (!waitingRef.current.includes(d.shop_id)) return;
    finishWaiting(d.shop_id);
    notify(`login:${d.shop_id}`, "danger", `${nameOf(d.shop_id)}：${d.reason}`);
  });

  const login = async (id: number) => {
    const key = `login:${id}`;
    await track(key, async () => {
      try {
        await api.post(`/api/shops/${id}/login`);
      } catch (e) {
        notify(key, "danger", `${nameOf(id)}：${errorText(e)}`);
        return;
      }
      setWaitingIds([...waitingRef.current.filter((x) => x !== id), id]);
      notify(key, "info", `${nameOf(id)}：请在弹出的浏览器窗口中扫码`);
      timers.current.set(
        id,
        setTimeout(() => {
          if (!waitingRef.current.includes(id)) return;
          finishWaiting(id);
          notify(key, "danger", `${nameOf(id)}：等待扫码超时，请重新发起扫码登录`);
        }, LOGIN_WAIT_TIMEOUT_MS),
      );
    });
  };

  /** 通用：调用接口，成功给出 text（可含后续刷新），失败显示原因。 */
  const run = async <T,>(action: string, id: number, call: () => Promise<T>, onOk: (r: T) => { tone: Notice["tone"]; text: string }) => {
    await track(`${action}:${id}`, async () => {
      try {
        const result = await call();
        const { tone, text } = onOk(result);
        notify(`${action}:${id}`, tone, `${nameOf(id)}：${text}`);
        await refreshShops();
      } catch (e) {
        notify(`${action}:${id}`, "danger", `${nameOf(id)}：${errorText(e)}`);
      }
    });
  };

  const probe = (id: number) =>
    run("probe", id, () => api.post<ShopRow>(`/api/shops/${id}/probe`), () => ({ tone: "success", text: "登录状态正常" }));

  const syncBase = (id: number) =>
    run("sync-base", id, () => api.post<Schemas["BaseSummary"]>(`/api/shops/${id}/sync-base`), (s) => ({
      tone: s.ready_for_label ? "success" : "warning",
      text:
        `发货资料已更新（地址 ${s.addresses}、快递 ${s.couriers}、模板 ${s.templates}、面单账户 ${s.accounts}）` +
        (s.ready_for_label ? "" : `，未就绪：${s.not_ready_reasons.join("；")}`),
    }));

  const checkEgress = (id: number, acceptChange = false) =>
    run(
      "egress-check",
      id,
      () => api.post<Schemas["EgressStatusOut"]>(`/api/shops/${id}/egress/check`, undefined, acceptChange ? { accept_change: true } : undefined),
      egressCheckResult,
    );

  const resume = (id: number) =>
    run("resume", id, () => api.post<ShopRow>(`/api/shops/${id}/resume`), () => ({ tone: "success", text: "已解除风控暂停" }));

  /** 设置出口：失败原因交给对话框就地显示，不进通知。 */
  const setEgress = async (id: number, request: EgressRequest): Promise<{ ok: boolean; error: string | null }> =>
    track(`egress:${id}`, async () => {
      try {
        await api.put<ShopRow>(`/api/shops/${id}/egress`, request);
      } catch (e) {
        return { ok: false, error: errorText(e) };
      }
      notify(`egress:${id}`, "success", `${nameOf(id)}：出口已保存，请检查出口`);
      await refreshShops();
      return { ok: true, error: null };
    });

  const addShop = async (
    input: Schemas["ShopCreate"],
  ): Promise<{ ok: true; shop: ShopRow } | { ok: false; error: string }> =>
    track("add", async () => {
      try {
        const shop = await api.post<ShopRow>("/api/shops", input);
        notify(`add:${shop.id}`, "success", `已添加「${shop.name}」，请先设置出口并检查通过，再扫码登录`);
        await refreshShops();
        return { ok: true as const, shop };
      } catch (e) {
        return { ok: false as const, error: errorText(e) };
      }
    });

  /** 改本地别名与手工维护字段：PATCH /api/shops/{id}。 */
  const updateShop = async (
    id: number,
    patch: {
      name: string;
      entity: string | null;
      platform_shop_id: string | null;
      bank_name: string | null;
      bank_tail: string | null;
    },
  ): Promise<{ ok: true; error: null } | { ok: false; error: string }> =>
    track(`edit:${id}`, async () => {
      try {
        await api.patch<ShopRow>(`/api/shops/${id}`, patch);
        notify(`edit:${id}`, "success", `${nameOf(id)}：已保存`);
        await refreshShops();
        return { ok: true as const, error: null };
      } catch (e) {
        return { ok: false as const, error: errorText(e) };
      }
    });

  /** 停用 / 启用：后端用 enabled 表达，重新启用时若出口被占用会被拒绝。 */
  const toggleEnabled = async (shop: ShopRow): Promise<void> => {
    const disable = shop.status !== "disabled";
    await track(`toggle:${shop.id}`, async () => {
      try {
        await api.patch<ShopRow>(`/api/shops/${shop.id}`, { enabled: !disable });
        notify(`toggle:${shop.id}`, "success", `${shop.name}：已${disable ? "停用" : "启用"}`);
        await refreshShops();
      } catch (e) {
        notify(`toggle:${shop.id}`, "danger", `${shop.name}：${errorText(e)}`);
      }
    });
  };

  /** 手动读取收款信息：平台只把它渲染在页面里，没有接口，失败可手填。 */
  const scrapeCard = async (id: number): Promise<void> => {
    await track(`scrape:${id}`, async () => {
      try {
        await api.post<ShopRow>(`/api/shops/${id}/profile/scrape`);
        notify(`scrape:${id}`, "success", `${nameOf(id)}：收款信息已同步`);
        await refreshShops();
      } catch (e) {
        notify(`scrape:${id}`, "danger", `${nameOf(id)}：${errorText(e)}`);
      }
    });
  };

  return {
    notices, dismissNotice, pending, waitingShopIds, login, probe, syncBase, checkEgress,
    resume, setEgress, addShop, updateShop, toggleEnabled, scrapeCard,
  };
}

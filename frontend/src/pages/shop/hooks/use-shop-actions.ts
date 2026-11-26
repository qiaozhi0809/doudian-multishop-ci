import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNoticeQueue, type QueuedNotice } from "@/components/custom/notice/use-notice-queue";
import type { ActionResult } from "@/lib/action-result";
import { api, errorText } from "@/lib/api-client";
import type { components } from "@/lib/api-types";
import { queryKeys } from "@/lib/query-keys";
import { useEventSubscription } from "@/lib/use-events";
import type { ShopRow } from "@/lib/use-shops";
import { egressCheckResult } from "../logic/egress-check-result";

type Schemas = components["schemas"];
type EgressRequest = Schemas["EgressRequest"];
export type ShopPatch = Schemas["ShopPatch"];
export type Notice = QueuedNotice;
type Outcome = { tone: Notice["tone"]; text: string };

const LOGIN_WAIT_TIMEOUT_MS = 10 * 60 * 1000;
const OK: ActionResult = { ok: true };

/** 店铺页的各项操作：结果交给右下角浮动提示；对话框里发起的操作失败时把原因交回对话框就地显示。 */
export function useShopActions(shops: ShopRow[]) {
  const client = useQueryClient();
  const { notices, notify, dismissNotice } = useNoticeQueue();
  const [pending, setPending] = useState<string[]>([]);
  const [waitingShopIds, setWaiting] = useState<number[]>([]);
  const waitingRef = useRef<number[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const shopsRef = useRef(shops);
  useEffect(() => {
    shopsRef.current = shops;
  });

  const nameOf = (id: number) => shopsRef.current.find((s) => s.id === id)?.name ?? `店铺 ${id}`;

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

  /**
   * 通用：调用接口，成功发提示并刷新店铺；失败时 inline=false 发提示，
   * inline=true（对话框里发起）只把原因交回去，由对话框就地显示。
   */
  const run = async <T,>(
    action: string,
    id: number,
    call: () => Promise<T>,
    onOk: (r: T) => Outcome,
    inline = false,
  ): Promise<ActionResult> =>
    track(`${action}:${id}`, async () => {
      const key = `${action}:${id}`;
      try {
        const result = await call();
        const { tone, text } = onOk(result);
        // 改了店名时用新名字提示（返回的是 ShopRow 就以它为准）
        const fresh = result as { id?: unknown; name?: unknown } | null;
        const name = fresh && fresh.id === id && typeof fresh.name === "string" ? fresh.name : nameOf(id);
        notify(key, tone, `${name}：${text}`);
      } catch (e) {
        if (!inline) notify(key, "danger", `${nameOf(id)}：${errorText(e)}`);
        return { ok: false as const, error: errorText(e) };
      }
      await refreshShops();
      return OK;
    });

  const done = (text: string) => (): Outcome => ({ tone: "success", text });

  const probe = (id: number) => run("probe", id, () => api.post<ShopRow>(`/api/shops/${id}/probe`), done("登录状态正常"));

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

  /** 恢复风控暂停：在确认对话框里发起，失败留在对话框。 */
  const resume = (id: number) => run("resume", id, () => api.post<ShopRow>(`/api/shops/${id}/resume`), done("已解除风控暂停"), true);

  /** 设置出口：失败原因交给对话框就地显示，不进提示。 */
  const setEgress = (id: number, request: EgressRequest) =>
    run("egress", id, () => api.put<ShopRow>(`/api/shops/${id}/egress`, request), done("出口已保存"), true);

  /** 各列表行里都带店铺名（也按它排序）：改名后一并刷新。 */
  const refreshNamedLists = () =>
    Promise.all(
      [queryKeys.ordersRoot(), queryKeys.labelPoolRoot(), queryKeys.aftersaleRoot(), queryKeys.productsRoot(),
        queryKeys.stockRoot(), queryKeys.fundRoot(), queryKeys.reconcileRoot()].map((queryKey) =>
        client.invalidateQueries({ queryKey }),
      ),
    );

  /** 改本地别名与手工维护字段：PATCH /api/shops/{id}。 */
  const updateShop = async (id: number, patch: ShopPatch) => {
    const result = await run("edit", id, () => api.patch<ShopRow>(`/api/shops/${id}`, patch), done("已保存"), true);
    if (result.ok && patch.name !== undefined) await refreshNamedLists();
    return result;
  };

  /** 停用 / 启用：后端用 enabled 表达，重新启用时若出口被占用会被拒绝。inline=true 时从确认对话框发起。 */
  const setEnabled = (id: number, enabled: boolean, inline = false) =>
    run("toggle", id, () => api.patch<ShopRow>(`/api/shops/${id}`, { enabled }), done(enabled ? "已启用" : "已停用"), inline);

  /** 开关接收飞鸽消息：开启从确认对话框发起（inline），关闭从菜单直接发起。 */
  const setIm = (id: number, enabled: boolean, inline = false) =>
    run(
      "im",
      id,
      () => api.patch<ShopRow>(`/api/shops/${id}`, { im_enabled: enabled }),
      done(enabled ? "已开启飞鸽消息" : "已关闭飞鸽消息"),
      inline,
    );

  /** 手动读取收款信息：平台只把它渲染在页面里，没有接口，失败可手填。 */
  const scrapeCard = (id: number) =>
    run("scrape", id, () => api.post<ShopRow>(`/api/shops/${id}/profile/scrape`), done("收款信息已同步"));

  const addShop = async (
    input: Schemas["ShopCreate"],
  ): Promise<{ ok: true; shop: ShopRow } | { ok: false; error: string }> =>
    track("add", async () => {
      try {
        const shop = await api.post<ShopRow>("/api/shops", input);
        notify(`add:${shop.id}`, "success", `已添加「${shop.name}」`);
        await refreshShops();
        return { ok: true as const, shop };
      } catch (e) {
        return { ok: false as const, error: errorText(e) };
      }
    });

  return {
    notices, notify, dismissNotice, pending, waitingShopIds, login, probe, syncBase, checkEgress,
    resume, setEgress, addShop, updateShop, setEnabled, setIm, scrapeCard,
  };
}

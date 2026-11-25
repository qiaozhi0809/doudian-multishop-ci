export interface AggregateSyncShops {
  shop_id: number;
  error?: string | null;
}

export interface AggregateSyncMessage {
  tone: "success" | "warning" | "info" | "danger";
  text: string;
}

/** 汇总一次跨店同步的结果；取不到的店单独说明，不能静默当成功。 */
export function summarizeSync(
  shops: AggregateSyncShops[],
  successText: (okCount: number) => string,
): AggregateSyncMessage {
  if (shops.length === 0) {
    return { tone: "info", text: "没有可同步的店铺（需先登录或解除暂停）" };
  }
  const failed = shops.filter((s) => s.error);
  const ok = shops.length - failed.length;
  if (ok === 0) {
    const reason = failed[0]?.error ?? "原因未知";
    return { tone: "danger", text: `同步失败：${reason}` };
  }
  if (failed.length > 0) {
    return { tone: "warning", text: `${ok} 家店同步成功，${failed.length} 家失败：${failed[0]?.error ?? "原因未知"}` };
  }
  return { tone: "success", text: successText(ok) };
}

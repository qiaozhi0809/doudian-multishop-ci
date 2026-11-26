import type { components } from "@/lib/api-types";
import type { ShopRow } from "@/lib/use-shops";

type EgressRequest = components["schemas"]["EgressRequest"];

export interface EgressForm {
  mode: "direct" | "proxy";
  entry: "pool" | "paste" | "fields";
  poolId: number | null;
  paste: string;
  scheme: "http" | "https";
  host: string;
  port: string;
  username: string;
  password: string;
  expiresAt: string;
}

export type EgressField = "poolId" | "paste" | "host" | "port" | "username" | "password" | "expiresAt";
export type EgressBuild =
  | { ok: true; request: EgressRequest }
  | { ok: false; errors: Partial<Record<EgressField, string>> };

export const emptyEgressForm = (): EgressForm => ({
  mode: "proxy",
  entry: "pool",
  poolId: null,
  paste: "",
  scheme: "http",
  host: "",
  port: "",
  username: "",
  password: "",
  expiresAt: "",
});

const PASTE_FORMAT = "代理商格式应为 IP|端口|账号|密码|到期日";
const PASTE_FIELDS = 5;

function isRealDate(value: string): boolean {
  if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(value)) return false;
  const d = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().startsWith(value);
}

/**
 * 把表单转成 PUT /api/shops/{id}/egress 的请求体，并在提交前做基本校验。
 * 只做格式层面的检查（详细规则以后端为准）；报错信息不回显账号密码。
 */
export function buildEgressRequest(form: EgressForm): EgressBuild {
  if (form.mode === "direct") return { ok: true, request: { mode: "direct" } };

  if (form.entry === "pool") {
    if (form.poolId === null) return { ok: false, errors: { poolId: "请选择池里的代理" } };
    return { ok: true, request: { mode: "proxy", pool_id: form.poolId } };
  }

  if (form.entry === "paste") {
    const line = form.paste.trim();
    const parts = line.split("|").map((p) => p.trim());
    if (parts.length !== PASTE_FIELDS || parts.some((p) => !p)) return { ok: false, errors: { paste: PASTE_FORMAT } };
    return { ok: true, request: { mode: "proxy", paste: line } };
  }

  const errors: Partial<Record<EgressField, string>> = {};
  const host = form.host.trim();
  const port = form.port.trim();
  if (!host) errors.host = "请输入代理主机";
  else if (host.includes("://")) errors.host = "主机不要带 http://，协议请在上方选择";
  if (!/^[0-9]+$/.test(port) || Number(port) < 1 || Number(port) > 65535) errors.port = "端口应为 1 到 65535 的数字";
  if (form.username && !form.password) errors.password = "填写了账号，请同时填写密码";
  if (form.expiresAt && !isRealDate(form.expiresAt)) errors.expiresAt = "到期日格式应为 YYYY-MM-DD";
  if (Object.keys(errors).length) return { ok: false, errors };

  const auth = form.username ? `${encodeURIComponent(form.username)}:${encodeURIComponent(form.password)}@` : "";
  const request: EgressRequest = { mode: "proxy", proxy_url: `${form.scheme}://${auth}${host}:${port}` };
  if (form.expiresAt) request.expires_at = form.expiresAt;
  return { ok: true, request };
}

/**
 * 同一时间最多一家启用中的店直连：别的店已占用直连时返回禁用原因（放在提示气泡里），否则 null。
 * selfId：正在设置出口的店本身（它自己在直连不算占用）；添加店铺时不传。
 */
export function directDisabledReason(shops: ShopRow[], selfId?: number): string | null {
  const holder = shops.find((s) => s.id !== selfId && s.egress_mode === "direct" && s.status !== "disabled");
  return holder ? `已有店铺「${holder.name}」使用直连，最多一家店可直连` : null;
}

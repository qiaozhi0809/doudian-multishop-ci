import { HOST_REASON, isValidHost, isValidPort, PORT_RANGE_REASON } from "./proxy-host";
import type { PoolItem, PoolPatch } from "../hooks/use-proxy-pool";

export interface EditForm {
  host: string;
  port: string;
  username: string;
  password: string;
  expires_at: string;
}

/** `主机:端口`（取最后一个冒号）。 */
export function splitDisplay(display: string): { host: string; port: string } {
  const i = display.lastIndexOf(":");
  return i < 0 ? { host: display, port: "" } : { host: display.slice(0, i), port: display.slice(i + 1) };
}

export function initialEditForm(item: PoolItem): EditForm {
  return { ...splitDisplay(item.proxy_display), username: "", password: "", expires_at: item.expires_at ?? "" };
}

export type EditField = "host" | "port";

/** 只带有改动的字段：账号密码不回显，留空即不改；到期日清空表示「不限期」。格式错误带 field，显示在对应输入框下。 */
export function buildPatch(
  item: PoolItem,
  form: EditForm,
): { ok: true; patch: PoolPatch } | { ok: false; error: string; field?: EditField } {
  const original = initialEditForm(item);
  const patch: PoolPatch = {};
  const host = form.host.trim();
  if (!host) return { ok: false, error: "请输入主机", field: "host" };
  if (!isValidHost(host)) return { ok: false, error: HOST_REASON, field: "host" };
  if (host !== original.host) patch.host = host;
  const port = form.port.trim();
  if (!/^[0-9]+$/.test(port)) return { ok: false, error: "端口必须是数字", field: "port" };
  if (!isValidPort(port)) return { ok: false, error: PORT_RANGE_REASON, field: "port" };
  if (port !== original.port) patch.port = Number(port);
  if (form.username.trim()) patch.username = form.username.trim();
  if (form.password) patch.password = form.password;
  if (form.expires_at !== original.expires_at) patch.expires_at = form.expires_at || null;
  if (Object.keys(patch).length === 0) return { ok: false, error: "没有需要保存的改动" };
  return { ok: true, patch };
}

export const HOST_REASON = "代理主机格式不正确";
export const PORT_RANGE_REASON = "端口必须在 1-65535 之间";

/** 与后端 `validate_proxy_host` 一致：含 `@ / ? # : [ ]` 或空白即不合法（暂不支持 IPv6）。 */
export function isValidHost(host: string): boolean {
  return host !== "" && !/[@/?#:[\]\s]/.test(host);
}

/** 端口为 1-65535 的整数（调用方已确认是纯数字）。 */
export function isValidPort(port: string): boolean {
  const n = Number(port);
  return n >= 1 && n <= 65535;
}

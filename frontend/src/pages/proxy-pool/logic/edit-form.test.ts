import type { PoolItem } from "../hooks/use-proxy-pool";
import { buildPatch, initialEditForm } from "./edit-form";

const item: PoolItem = {
  id: 1, proxy_display: "1.2.3.4:8080", expires_at: "2026-12-31", expiry_state: "ok",
  in_use_by: null, last_checked_at: null, last_check_ip: null,
};

describe("edit-form", () => {
  it("初始值来自 proxy_display 与到期日，账号密码为空", () => {
    expect(initialEditForm(item)).toEqual({ host: "1.2.3.4", port: "8080", username: "", password: "", expires_at: "2026-12-31" });
  });
  it("只发送有改动或非空的字段", () => {
    const form = { ...initialEditForm(item), port: "9090", password: "new" };
    expect(buildPatch(item, form)).toEqual({ ok: true, patch: { port: 9090, password: "new" } });
  });
  it("清空到期日发 null", () => {
    expect(buildPatch(item, { ...initialEditForm(item), expires_at: "" })).toEqual({ ok: true, patch: { expires_at: null } });
  });
  it("没有改动或端口非法时报错", () => {
    expect(buildPatch(item, initialEditForm(item))).toEqual({ ok: false, error: "没有需要保存的改动" });
    expect(buildPatch(item, { ...initialEditForm(item), port: "8a" })).toEqual({ ok: false, error: "端口必须是数字" });
  });
  it("主机含 @ 等字符或为 IPv6 时拒绝", () => {
    for (const host of ["x@5.6.7.8", "a/b", "a?b", "a#b", "a:b", "[::1]", "a b"]) {
      expect(buildPatch(item, { ...initialEditForm(item), host })).toEqual({ ok: false, error: "代理主机格式不正确" });
    }
  });
  it("端口超出 1-65535 时拒绝", () => {
    for (const port of ["0", "65536"]) {
      expect(buildPatch(item, { ...initialEditForm(item), port })).toEqual({ ok: false, error: "端口必须在 1-65535 之间" });
    }
    expect(buildPatch(item, { ...initialEditForm(item), port: "65535" })).toEqual({ ok: true, patch: { port: 65535 } });
  });
});

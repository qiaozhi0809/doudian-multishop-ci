import { buildEgressRequest, emptyEgressForm, type EgressForm } from "./egress-form";

const proxyFields = (o: Partial<EgressForm> = {}): EgressForm => ({
  ...emptyEgressForm(),
  mode: "proxy",
  entry: "fields",
  host: "1.2.3.4",
  port: "8000",
  username: "user",
  password: "pass",
  expiresAt: "2026-12-01",
  ...o,
});

describe("buildEgressRequest", () => {
  it("直连只提交方式", () => {
    expect(buildEgressRequest({ ...emptyEgressForm(), mode: "direct" })).toEqual({ ok: true, request: { mode: "direct" } });
  });

  it("默认入口是从池选择", () => {
    expect(emptyEgressForm()).toMatchObject({ entry: "pool", poolId: null });
  });

  it("从池选择：选了提交 pool_id", () => {
    expect(buildEgressRequest({ ...emptyEgressForm(), poolId: 7 })).toEqual({ ok: true, request: { mode: "proxy", pool_id: 7 } });
  });

  it("从池选择：没选时提示", () => {
    expect(buildEgressRequest(emptyEgressForm())).toEqual({ ok: false, errors: { poolId: "请选择池里的代理" } });
  });

  it("粘贴代理商一行：提交 paste 字段", () => {
    const line = "1.2.3.4|8000|user|pass|2026-12-01";
    expect(buildEgressRequest({ ...emptyEgressForm(), mode: "proxy", entry: "paste", paste: `  ${line}\n` })).toEqual({
      ok: true,
      request: { mode: "proxy", paste: line },
    });
  });

  it("粘贴内容不是 5 段时提示格式，并且报错里不带账号密码", () => {
    const r = buildEgressRequest({ ...emptyEgressForm(), mode: "proxy", entry: "paste", paste: "1.2.3.4|8000|user|secret" });
    expect(r).toEqual({ ok: false, errors: { paste: "代理商格式应为 IP|端口|账号|密码|到期日" } });
    expect(JSON.stringify(r)).not.toContain("secret");
  });

  it("粘贴为空时提示", () => {
    const r = buildEgressRequest({ ...emptyEgressForm(), mode: "proxy", entry: "paste", paste: " " });
    expect(r).toMatchObject({ ok: false, errors: { paste: expect.any(String) } });
  });

  it("分项填写：拼成 http 代理地址并对账号密码编码", () => {
    const r = buildEgressRequest(proxyFields({ username: "us er", password: "p@ss:/word" }));
    expect(r).toEqual({
      ok: true,
      request: { mode: "proxy", proxy_url: "http://us%20er:p%40ss%3A%2Fword@1.2.3.4:8000", expires_at: "2026-12-01" },
    });
  });

  it("分项填写：支持 https，无账号密码时不带认证段，到期日可空", () => {
    const r = buildEgressRequest(proxyFields({ scheme: "https", username: "", password: "", expiresAt: "" }));
    expect(r).toEqual({ ok: true, request: { mode: "proxy", proxy_url: "https://1.2.3.4:8000" } });
  });

  it.each([
    [{ host: "" }, "host"],
    [{ host: "http://1.2.3.4" }, "host"],
    [{ port: "" }, "port"],
    [{ port: "80a" }, "port"],
    [{ port: "70000" }, "port"],
    [{ expiresAt: "2026/12/01" }, "expiresAt"],
    [{ expiresAt: "2026-13-40" }, "expiresAt"],
  ] as const)("分项填写校验：%j → %s 报错", (override, field) => {
    const r = buildEgressRequest(proxyFields(override));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(Object.keys(r.errors)).toContain(field);
  });

  it("只有账号没有密码时提示", () => {
    const r = buildEgressRequest(proxyFields({ password: "" }));
    expect(r).toMatchObject({ ok: false, errors: { password: expect.any(String) } });
  });
});

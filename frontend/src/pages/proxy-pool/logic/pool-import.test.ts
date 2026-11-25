import { previewImport } from "./pool-import";

const good = "1.2.3.4|8080|user|pass|2026-12-31";

describe("previewImport", () => {
  it("统计总行数与有效行，空行不计入 total", () => {
    expect(previewImport(`${good}\n\n   \n${good}\n`)).toEqual({ total: 2, valid: 2, errors: [] });
  });

  it("第 3、7 行有错时给出原始行号 [3,7]", () => {
    const text = [good, good, "bad", good, "", good, "1.2.3.4|80|u|p|2026-13-40", good].join("\n");
    const result = previewImport(text);
    expect(result.errors.map((e) => e.line)).toEqual([3, 7]);
    expect(result.total).toBe(7);
    expect(result.valid).toBe(5);
  });

  it("按后端规则报原因：段数、端口、到期日", () => {
    const r = previewImport("1.2.3.4|80|u|p\n1.2.3.4|8a|u|p|2026-01-01\n1.2.3.4|80|u|p|2026-02-30\n1.2.3.4|80||p|2026-01-01");
    expect(r.errors).toEqual([
      { line: 1, reason: "格式应为 IP|端口|账号|密码|到期日" },
      { line: 2, reason: "端口必须是数字" },
      { line: 3, reason: "到期日格式应为 YYYY-MM-DD" },
      { line: 4, reason: "格式应为 IP|端口|账号|密码|到期日" },
    ]);
  });

  it("行尾 \\r 被去掉；只按 \\n 切分", () => {
    expect(previewImport(`${good}\r\n${good}\r\n`)).toEqual({ total: 2, valid: 2, errors: [] });
  });

  it("空文本全为 0", () => {
    expect(previewImport("")).toEqual({ total: 0, valid: 0, errors: [] });
  });
});

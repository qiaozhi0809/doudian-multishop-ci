import { HOST_REASON, isValidHost, isValidPort, PORT_RANGE_REASON } from "./proxy-host";

export interface ImportPreview {
  total: number;
  valid: number;
  errors: { line: number; reason: string }[];
}

const FORMAT_REASON = "格式应为 IP|端口|账号|密码|到期日";

/** 与后端 `parse_provider_line` 一致：5 段均非空、主机合法、端口 1-65535、到期日是真实日期。返回错误原因或 null。 */
function lineError(raw: string): string | null {
  const parts = raw.trim().split("|").map((p) => p.trim());
  if (parts.length !== 5 || parts.some((p) => !p)) return FORMAT_REASON;
  if (!isValidHost(parts[0])) return HOST_REASON;
  if (!/^\d+$/.test(parts[1])) return "端口必须是数字";
  if (!isValidPort(parts[1])) return PORT_RANGE_REASON;
  if (!isRealDate(parts[4])) return "到期日格式应为 YYYY-MM-DD";
  return null;
}

function isRealDate(value: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d;
}

/**
 * 提交前预览导入文本。计数口径与后端一致：只按 `\n` 切分、去行尾 `\r`、
 * 空行跳过（不计入 total），行号是原文的 1 起始行号。
 */
export function previewImport(text: string): ImportPreview {
  const errors: ImportPreview["errors"] = [];
  let total = 0;
  text.split("\n").forEach((rawLine, index) => {
    const raw = rawLine.replace(/\r$/, "");
    if (!raw.trim()) return;
    total += 1;
    const reason = lineError(raw);
    if (reason) errors.push({ line: index + 1, reason });
  });
  return { total, valid: total - errors.length, errors };
}

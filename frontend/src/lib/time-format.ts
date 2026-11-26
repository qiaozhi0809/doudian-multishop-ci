import { EMPTY_TEXT as EMPTY } from "@/lib/empty-text";

const bjFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const HAS_ZONE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

/** ISO-8601（后端为 UTC）→ 北京时间 `YYYY-MM-DD HH:mm`，与浏览器时区无关；空值或无效值显示「暂无」。 */
export function formatBjTime(iso: string | null): string {
  if (!iso) return EMPTY;
  const date = new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(date.getTime())) return EMPTY;
  const p = Object.fromEntries(bjFormatter.formatToParts(date).map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

const DAY_MS = 86_400_000;
const HOUR_MS = 3_600_000;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** 到期时刻：只有日期的到期日当天整天有效（北京时间当天结束），与后端判定一致。 */
export function parseExpiry(iso: string): Date {
  if (DATE_ONLY.test(iso)) return new Date(new Date(`${iso}T00:00:00+08:00`).getTime() + DAY_MS);
  return new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
}

/** 距到期的天数，向上取整；已过期为 0 或负数。 */
export function daysUntil(iso: string, now: Date = new Date()): number {
  return Math.ceil((parseExpiry(iso).getTime() - now.getTime()) / DAY_MS);
}

/** 剩余时间：「剩 N 天」「剩 N 小时」，过期为「已过期」，空值或无效值为「暂无」。 */
export function formatRemaining(iso: string | null, now: Date = new Date()): string {
  if (!iso) return EMPTY;
  const ms = parseExpiry(iso).getTime() - now.getTime();
  if (Number.isNaN(ms)) return EMPTY;
  if (ms <= 0) return "已过期";
  if (ms < DAY_MS) return `剩 ${Math.max(1, Math.ceil(ms / HOUR_MS))} 小时`;
  return `剩 ${Math.ceil(ms / DAY_MS)} 天`;
}

/** 北京时间今天的只显示 `HH:mm`，其余显示完整时间（悬停再显示完整时间，ui-guidelines 第 6 节）。 */
export function formatBjTimeSmart(iso: string | null, now: Date = new Date()): string {
  const full = formatBjTime(iso);
  if (full === EMPTY) return EMPTY;
  const today = formatBjTime(now.toISOString()).slice(0, 10);
  return full.startsWith(today) ? full.slice(11) : full;
}

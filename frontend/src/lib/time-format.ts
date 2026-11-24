const EMPTY = "暂无";

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

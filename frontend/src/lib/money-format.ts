/** 整数分 → `¥1,234.56`；负数为 `-¥5.00`。金额一律以整数分传递，只在展示时换算。 */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const yuan = Math.trunc(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const fen = (abs % 100).toString().padStart(2, "0");
  return `${sign}¥${yuan}.${fen}`;
}

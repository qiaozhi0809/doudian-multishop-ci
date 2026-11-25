/** 指标卡的含义色（见 styles.css 的 .kpi-dot）。 */
export type KpiTone = "info" | "warning" | "danger" | "success" | "violet" | "neutral";

/** 黄、红两类只在有数时亮，0 时变灰。 */
export function isQuiet(tone: KpiTone, value: number | null | undefined): boolean {
  return (tone === "warning" || tone === "danger") && !value;
}

export function KpiDot({ tone, value }: { tone: KpiTone; value?: number | null }) {
  return <span className="kpi-dot" data-tone={tone} data-quiet={isQuiet(tone, value) || undefined} aria-hidden="true" />;
}

import type { CostBreakdown, Decimal } from "./types";

export const num = (value: Decimal | number | null | undefined): number =>
  value === null || value === undefined ? Number.NaN : Number(value);

export const total = (costs: CostBreakdown): number =>
  num(costs.model_usd) + num(costs.infra_usd) + num(costs.data_usd);

export function usd(value: number, digits = 4): string {
  if (!Number.isFinite(value)) return "—";
  return `$${value.toFixed(digits)}`;
}

export function pct(rate: number | null | undefined, digits = 1): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return "—";
  return `${(rate * 100).toFixed(digits)}%`;
}

export function signedPct(change: number, digits = 1): string {
  if (!Number.isFinite(change)) return "—";
  const sign = change > 0 ? "+" : change < 0 ? "−" : "±";
  return `${sign}${Math.abs(change).toFixed(digits)}%`;
}

export function changePct(before: number, after: number): number {
  return before === 0 ? Number.NaN : ((after - before) / before) * 100;
}

export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`;
}

export function compact(value: number): string {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function humanize(identifier: string): string {
  return identifier.replaceAll("_", " ");
}

/** Guardrail details carry raw floats; trim them to four decimals. */
export function prettyDetail(detail: string): string {
  return detail.replace(/(\d+\.\d{4})\d+/g, "$1");
}

export function jsonInline(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll('":', '": ')
    .replaceAll(",", ", ");
}

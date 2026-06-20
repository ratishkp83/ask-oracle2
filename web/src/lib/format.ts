// Deterministic, local formatting for the executive surface. No locale guessing
// beyond en-US; all numbers render tabular (the `.num` class) for alignment.
const NF = new Intl.NumberFormat("en-US");
const NF2 = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function isNumeric(v: unknown): boolean {
  if (typeof v === "number") return Number.isFinite(v);
  if (typeof v === "string" && v.trim() !== "") return Number.isFinite(Number(v));
  return false;
}

export function toNumber(v: unknown): number {
  return typeof v === "number" ? v : Number(v);
}

export function formatInt(n: number): string {
  return NF.format(Math.round(n));
}

export function formatNumber(n: number): string {
  return Number.isInteger(n) ? NF.format(n) : NF2.format(n);
}

export function formatCompact(n: number, currency = false): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const pfx = currency ? "$" : "";
  if (abs >= 1_000_000_000) return `${sign}${pfx}${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}${pfx}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}${pfx}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${pfx}${formatNumber(abs)}`;
}

export function formatPercent(n: number): string {
  return `${NF2.format(n)}%`;
}

export function formatMs(seconds: number): string {
  const ms = seconds * 1000;
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`;
}

export function formatCell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return formatNumber(v);
  return String(v);
}

// "DAYS_OVERDUE" -> "Days overdue" (sentence case, underscores to spaces).
export function humanize(name: string): string {
  return name.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase());
}

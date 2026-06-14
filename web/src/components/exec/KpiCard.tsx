import { Kpi } from "@/lib/derive/kpis";

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className="rounded-card border border-hairline bg-surface px-4 py-3.5">
      <div className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted" title={kpi.label}>
        {kpi.label}
      </div>
      <div className="num mt-1.5 font-display text-[26px] font-semibold leading-none tracking-[-0.01em] text-ink">
        {kpi.value}
      </div>
      <div className="mt-1.5 text-[11.5px] text-ink-faint">{kpi.context}</div>
    </div>
  );
}

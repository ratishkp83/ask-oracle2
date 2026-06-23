import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartSpec } from "@/lib/derive/chart";
import { formatCompact, humanize } from "@/lib/format";

// Leaf visual — concrete hex (SVG fill doesn't reliably resolve CSS vars).
const PETROL = "#0E5C63";
const GRID = "#EDEAE3";
const TICK = "#8A9099";
const INK = "#16191F";

export function DriverChart({ spec, onBarClick }: { spec: ChartSpec; onBarClick?: (label: string) => void }) {
  const fmt = (v: number) => formatCompact(v, spec.currency);
  const drillable = spec.type === "bar" && !!onBarClick;
  const title =
    spec.type === "line"
      ? `${humanize(spec.measureName)} over ${humanize(spec.dimensionName)}`
      : `${humanize(spec.measureName)} by ${humanize(spec.dimensionName)}`;
  // Bar chart height scales with bars (≈26px each); line is fixed and compact.
  const height = spec.type === "bar" ? Math.min(spec.data.length, 8) * 26 + 8 : 150;

  return (
    <div className="rounded-card border border-hairline bg-surface px-4 py-3.5">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
          {title}
          {spec.type === "bar" && spec.data.length > 1 ? " — top " + spec.data.length : ""}
        </span>
        {drillable ? (
          <span className="text-[11px] text-ink-faint">Select a bar to drill in</span>
        ) : (
          spec.extra > 0 && <span className="text-[11px] text-ink-faint">+{spec.extra} more</span>
        )}
      </div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "bar" ? (
            <BarChart layout="vertical" data={spec.data} margin={{ top: 0, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid horizontal={false} stroke={GRID} />
              <XAxis type="number" tickFormatter={fmt} tick={{ fontSize: 11, fill: TICK }} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="label"
                width={118}
                interval={0}
                tick={{ fontSize: 12, fill: INK }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: string) => (v.length > 16 ? v.slice(0, 15) + "…" : v)}
              />
              <Tooltip cursor={{ fill: "#F1EFEA" }} content={<ChartTip fmt={fmt} drill={drillable} />} />
              <Bar
                dataKey="value"
                fill={PETROL}
                radius={[0, 4, 4, 0]}
                barSize={16}
                cursor={drillable ? "pointer" : undefined}
                onClick={drillable ? (d: any) => onBarClick?.(d?.label ?? d?.payload?.label) : undefined}
              />
            </BarChart>
          ) : (
            <LineChart data={spec.data} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: TICK }} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: TICK }} axisLine={false} tickLine={false} width={52} />
              <Tooltip content={<ChartTip fmt={fmt} />} />
              <Line type="monotone" dataKey="value" stroke={PETROL} strokeWidth={2} dot={false} activeDot={{ r: 4, fill: PETROL }} />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ChartTip({ active, payload, label, fmt, drill }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-control border border-hairline bg-surface px-2.5 py-1.5 shadow-e2">
      <div className="text-[11px] text-ink-muted">{label}</div>
      <div className="num text-[13px] font-medium text-ink">{fmt(payload[0].value)}</div>
      {drill && <div className="mt-0.5 text-[10.5px] text-brand">Click to drill in →</div>}
    </div>
  );
}

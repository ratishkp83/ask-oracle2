import { Sparkles } from "lucide-react";
import { Insight } from "@/lib/derive/insight";

// The "what stands out" band — a compact, premium strip of locally-derived facts
// shown above the KPI cards (ADR-027, charter D-H). Each item carries a factual
// `basis` as a tooltip. Renders nothing when there are no insights, so it never
// adds height to a result that has nothing notable to say.
export function InsightBand({ insights }: { insights: Insight[] }) {
  if (insights.length === 0) return null;
  return (
    <div
      className="shrink-0 rounded-card border border-hairline border-l-[3px] border-l-brand bg-brand-weak px-3.5 py-2.5"
      role="note"
      aria-label="What stands out"
    >
      <div className="flex items-center gap-1.5">
        <Sparkles className="h-3.5 w-3.5 text-brand" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-brand">
          What stands out
        </span>
      </div>
      <ul className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1">
        {insights.map((it, i) => (
          <li key={i} className="text-[12.5px] leading-snug text-ink" title={it.basis}>
            {it.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

import { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";

// First-run lands here (B-5): ask a question, not admin setup. The propose→run
// flow (nl2sql → review → /execute → executive results) is wired in B5; for now
// this is the premium entry surface.
const EXAMPLES = [
  "Top customers by outstanding AR this year",
  "Monthly AP spend by supplier, last 12 months",
  "Overdue invoices over 30 days, by org",
];

export function AskPage() {
  const [q, setQ] = useState("");

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl animate-fade-in">
        <div className="mb-1.5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
          <Sparkles className="h-3.5 w-3.5 text-brand" /> Ask in plain English
        </div>
        <h1 className="font-display text-[28px] font-semibold leading-tight tracking-[-0.015em] text-ink">
          What would you like to know?
        </h1>
        <p className="mt-2 text-[14px] leading-relaxed text-ink-muted">
          Ask a question about your Oracle data. We propose read-only SQL for your review —
          nothing runs until you approve it.
        </p>

        <div className="mt-5 rounded-card border border-hairline bg-surface p-3 shadow-e1">
          <textarea
            value={q}
            onChange={(e) => setQ(e.target.value)}
            rows={3}
            placeholder="e.g. Top 10 customers by outstanding receivables for FY26"
            className="w-full resize-none bg-transparent px-2 py-1 text-[15px] text-ink outline-none placeholder:text-ink-faint"
          />
          <div className="flex items-center justify-between px-2 pt-1">
            <span className="text-[12px] text-ink-faint">AI proposes · you approve · read-only</span>
            <button
              type="button"
              disabled={!q.trim()}
              className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity disabled:opacity-40"
            >
              Generate SQL <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setQ(ex)}
              className="rounded-full border border-hairline bg-surface px-3 py-1.5 text-[12.5px] text-ink-muted transition-colors hover:border-brand hover:text-ink"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

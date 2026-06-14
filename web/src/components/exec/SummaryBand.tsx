import { useState } from "react";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { ExecuteResult } from "@/lib/api/schemas";
import { formatInt, formatMs } from "@/lib/format";

// Band 1 (B-6): the question as headline + deterministic run meta + the exact SQL
// behind a disclosure. No LLM-written prose — everything here is computed locally.
export function SummaryBand({
  question,
  sql,
  result,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
}) {
  const [showSql, setShowSql] = useState(false);
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Result</div>
      <h1 className="mt-1 font-display text-[21px] font-semibold leading-tight tracking-[-0.015em] text-ink">
        {question}
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12.5px] text-ink-muted">
        <span className="num">
          {formatInt(result.row_count)} rows · {result.columns.length} columns · {formatMs(result.elapsed_seconds)}
        </span>
        {result.truncated && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FBEEDD] px-2.5 py-0.5 text-[11.5px] font-medium text-warn">
            <AlertTriangle className="h-3 w-3" /> First {formatInt(result.row_count)} shown
          </span>
        )}
        <button
          type="button"
          onClick={() => setShowSql((s) => !s)}
          className="inline-flex items-center gap-1 font-medium text-brand"
        >
          <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showSql ? "rotate-90" : ""}`} />
          {showSql ? "Hide SQL" : "View SQL"}
        </button>
      </div>
      {showSql && (
        <pre className="mt-2 max-h-24 overflow-auto rounded-control bg-surface-sunken px-3 py-2 font-mono text-[12px] leading-relaxed text-ink-muted">
          {sql}
        </pre>
      )}
    </div>
  );
}

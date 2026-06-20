import { useState } from "react";
import { AlertTriangle, ArrowLeft, ChevronDown, Loader2, Play, ShieldCheck } from "lucide-react";
import type { Confidence } from "@/lib/api/schemas";

export interface StepError {
  message: string;
  errorId?: string;
}

// The approve-before-run gate (invariant 2): the AI proposes (or we deterministically
// build a pull-detail wrap) read-only SQL and the user reviews — and may edit — it
// before anything executes. Confidence + the explanation are advisory; the editable
// SQL is the contract. "Run query" is the only path to /execute and is disabled until
// a connection is chosen (E10). `binds` (pull-detail) are shown read-only so the user
// sees what the :pN placeholders resolve to.
export function ProposedSql({
  question,
  interpretedQuestion,
  eyebrow = "Review proposed SQL",
  confidence,
  explanation,
  binds,
  sql,
  onSqlChange,
  onRun,
  onBack,
  running,
  canRun,
  error,
}: {
  question: string;
  interpretedQuestion?: string | null;
  eyebrow?: string;
  confidence?: Confidence;
  explanation?: string | null;
  binds?: Record<string, unknown>;
  sql: string;
  onSqlChange: (v: string) => void;
  onRun: () => void;
  onBack: () => void;
  running: boolean;
  canRun: boolean;
  error: StepError | null;
}) {
  const runnable = canRun && !running && sql.trim().length > 0;
  const bindEntries = binds ? Object.entries(binds) : [];
  const interp = interpretedQuestion?.trim();
  const headline = interp || question;
  const normQ = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();
  const showAsked = !!interp && normQ(interp) !== normQ(question);

  return (
    <div className="flex h-full flex-col px-6 py-5">
      <div className="mx-auto flex h-full w-full max-w-3xl flex-col">
        {/* Header: the question being answered + a way back to edit it. */}
        <div className="flex shrink-0 items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
              {eyebrow}
            </div>
            <h2 className="mt-1 truncate font-display text-[20px] font-semibold tracking-[-0.01em] text-ink">
              {headline}
            </h2>
            {showAsked && (
              <p className="mt-0.5 truncate text-[12px] text-ink-faint">
                You asked: <span className="italic">“{question}”</span>
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onBack}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-surface-sunken"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
        </div>

        <ConfidenceBlock confidence={confidence ?? null} explanation={explanation} />

        {/* The editable SQL — the deliberate human gate. Only the textarea scrolls. */}
        <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-card border border-hairline bg-surface">
          <div className="flex shrink-0 items-center justify-between border-b border-hairline px-3.5 py-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
              SQL · read-only · editable
            </span>
            <span className="inline-flex items-center gap-1 text-[11.5px] text-ink-faint">
              <ShieldCheck className="h-3.5 w-3.5 text-gain" /> SELECT-only enforced server-side
            </span>
          </div>
          <textarea
            aria-label="Proposed SQL"
            value={sql}
            onChange={(e) => onSqlChange(e.target.value)}
            disabled={running}
            spellCheck={false}
            className="min-h-0 flex-1 resize-none bg-transparent p-3.5 font-mono text-[13px] leading-relaxed text-ink outline-none disabled:opacity-60"
          />
        </div>

        {bindEntries.length > 0 && (
          <div className="mt-2 flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-ink-faint">
            <span className="font-medium uppercase tracking-[0.06em]">Bound values</span>
            {bindEntries.map(([k, v]) => (
              <span key={k} className="num rounded-control border border-hairline bg-surface px-2 py-0.5 text-ink-muted">
                :{k} = {String(v)}
              </span>
            ))}
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="mt-3 flex shrink-0 items-start gap-2 rounded-card border border-loss/30 bg-loss/5 px-3.5 py-2.5 text-[12.5px] text-ink"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-loss" />
            <span>
              {error.message}
              {error.errorId && (
                <span className="mt-0.5 block text-[11px] text-ink-faint">
                  Reference: <span className="num">{error.errorId}</span>
                </span>
              )}
            </span>
          </div>
        )}

        <div className="mt-3 flex shrink-0 items-center justify-between gap-3">
          <span className="text-[12px] text-ink-faint">
            {canRun ? "Nothing runs until you approve." : "Select a connection above to run."}
          </span>
          <button
            type="button"
            onClick={onRun}
            disabled={!runnable}
            title={canRun ? undefined : "No connection selected"}
            className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white transition-opacity disabled:opacity-40"
          >
            {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {running ? "Running…" : "Run query"}
          </button>
        </div>
      </div>
    </div>
  );
}

const TONE: Record<string, { dot: string; text: string }> = {
  high: { dot: "bg-gain", text: "text-gain" },
  medium: { dot: "bg-warn", text: "text-warn" },
  low: { dot: "bg-loss", text: "text-loss" },
};

// Confidence is advisory: a colored level chip with collapsible reasons, plus the
// plain-English explanation. Never a gate — the SQL review is.
function ConfidenceBlock({
  confidence,
  explanation,
}: {
  confidence: Confidence;
  explanation?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const reasons = confidence?.reasons ?? [];
  const tone = confidence ? TONE[confidence.level.toLowerCase()] ?? { dot: "bg-ink-faint", text: "text-ink-muted" } : null;

  if (!confidence && !explanation) return null;

  return (
    <div className="mt-4 shrink-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        {confidence && tone && (
          <button
            type="button"
            onClick={() => reasons.length > 0 && setOpen((v) => !v)}
            aria-expanded={reasons.length > 0 ? open : undefined}
            className={`inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface px-2.5 py-1 text-[12px] font-medium ${tone.text} ${
              reasons.length > 0 ? "hover:border-brand" : "cursor-default"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
            {confidence.level} confidence
            {reasons.length > 0 && (
              <ChevronDown className={`h-3.5 w-3.5 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`} />
            )}
          </button>
        )}
        {explanation && <p className="min-w-0 flex-1 text-[12.5px] leading-relaxed text-ink-muted">{explanation}</p>}
      </div>

      {open && reasons.length > 0 && (
        <ul className="mt-2 space-y-1 rounded-card border border-hairline bg-surface-sunken px-3.5 py-2.5 text-[12px] text-ink-muted">
          {reasons.map((r, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-ink-faint">·</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

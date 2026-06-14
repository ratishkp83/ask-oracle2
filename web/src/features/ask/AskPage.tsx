import { useState } from "react";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { ResultsView } from "@/components/exec/ResultsView";
import { nl2sql, execute } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import type { ExecuteResult, Nl2SqlResult } from "@/lib/api/schemas";
import { useSession } from "@/app/session";
import { SchemaPicker } from "./SchemaPicker";
import { ProposedSql, StepError } from "./ProposedSql";
import { SAMPLE_QUESTION, SAMPLE_RESULT, SAMPLE_SQL } from "./sampleResult";

// First-run lands here (B-5): ask a question, not admin setup. The live flow is a
// small state machine — idle → proposing → review → running → results — gated by a
// human SQL approval in the middle (invariant 2). "See a sample result" previews
// the executive Results design with no DB.
const EXAMPLES = [
  "Top customers by outstanding AR this year",
  "Monthly AP spend by supplier, last 12 months",
  "Overdue invoices over 30 days, by org",
];

type AskState =
  | { kind: "idle" }
  | { kind: "proposing"; question: string }
  | { kind: "review"; question: string; proposal: Nl2SqlResult; sql: string }
  | { kind: "running"; question: string; proposal: Nl2SqlResult; sql: string }
  | { kind: "results"; question: string; sql: string; result: ExecuteResult }
  | { kind: "demo" };

type PhaseError = (StepError & { phase: "propose" | "run" }) | null;

// Sanitize any failure into the E9 shape (friendly message + error_id), never raw.
function toStepError(e: unknown): StepError {
  if (e instanceof ApiError) return { message: e.message, errorId: e.errorId };
  return { message: "Something went wrong. Please try again." };
}

export function AskPage() {
  const { profileId, schemaId } = useSession();
  const [q, setQ] = useState("");
  const [state, setState] = useState<AskState>({ kind: "idle" });
  const [error, setError] = useState<PhaseError>(null);

  function reset() {
    setError(null);
    setState({ kind: "idle" });
  }

  async function generate() {
    const question = q.trim();
    if (!question) return;
    setError(null);
    setState({ kind: "proposing", question });
    try {
      const proposal = await nl2sql({
        natural_language: question,
        schema_id: schemaId ?? undefined,
      });
      setState({ kind: "review", question, proposal, sql: proposal.sql });
    } catch (e) {
      setError({ ...toStepError(e), phase: "propose" });
      setState({ kind: "idle" });
    }
  }

  async function run() {
    if (state.kind !== "review" || !profileId) return;
    const { question, proposal, sql } = state;
    setError(null);
    setState({ kind: "running", question, proposal, sql });
    try {
      const result = await execute({ sql, profile_id: profileId });
      setState({ kind: "results", question, sql, result });
    } catch (e) {
      setError({ ...toStepError(e), phase: "run" });
      setState({ kind: "review", question, proposal, sql });
    }
  }

  if (state.kind === "demo") {
    return (
      <ResultsView
        question={SAMPLE_QUESTION}
        sql={SAMPLE_SQL}
        result={SAMPLE_RESULT}
        onBack={reset}
        onPullQuery={(query) => {
          setQ(query);
          reset();
        }}
      />
    );
  }

  if (state.kind === "results") {
    return <ResultsView question={state.question} sql={state.sql} result={state.result} onBack={reset} />;
  }

  if (state.kind === "review" || state.kind === "running") {
    return (
      <ProposedSql
        question={state.question}
        proposal={state.proposal}
        sql={state.sql}
        onSqlChange={(v) =>
          setState((s) => (s.kind === "review" ? { ...s, sql: v } : s))
        }
        onRun={run}
        onBack={reset}
        running={state.kind === "running"}
        canRun={!!profileId}
        error={error?.phase === "run" ? error : null}
      />
    );
  }

  // idle / proposing — the ask form.
  const busy = state.kind === "proposing";
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 pb-[16vh]">
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
          <div className="mb-1 border-b border-hairline px-2 pb-2">
            <SchemaPicker />
          </div>
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
              onClick={generate}
              disabled={!q.trim() || busy}
              className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {busy ? "Proposing…" : "Generate SQL"}
              {!busy && <ArrowRight className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {error?.phase === "propose" && (
          <div
            role="alert"
            className="mt-3 rounded-card border border-loss/30 bg-loss/5 px-3.5 py-2.5 text-[12.5px] text-ink"
          >
            {error.message}
            {error.errorId && (
              <span className="mt-0.5 block text-[11px] text-ink-faint">
                Reference: <span className="num">{error.errorId}</span>
              </span>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
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

        <button
          type="button"
          onClick={() => setState({ kind: "demo" })}
          className="mt-5 text-[12.5px] font-medium text-brand hover:underline"
        >
          See a sample result →
        </button>
      </div>
    </div>
  );
}

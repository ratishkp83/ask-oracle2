import { useState } from "react";
import { ArrowRight, Loader2, Sparkles, Zap } from "lucide-react";
import { ResultsView } from "@/components/exec/ResultsView";
import { nl2sql, execute } from "@/lib/api/endpoints";
import { friendlyError } from "@/lib/api/client";
import type { Confidence, ExecuteResult } from "@/lib/api/schemas";
import { buildPullDetailSql, PullFilter } from "@/lib/derive/pullDetail";
import { useSession } from "@/app/session";
import { SchemaPicker } from "./SchemaPicker";
import { ProposedSql, StepError } from "./ProposedSql";
import { SAMPLE_QUESTION, SAMPLE_RESULT, SAMPLE_SQL } from "./sampleResult";

// First-run lands here (B-5): ask a question, not admin setup. The live flow is a
// small state machine — idle → proposing → review → running → results — gated by a
// human SQL approval in the middle. The Auto-run toggle (ADR: human stays in control
// by choosing the mode) skips that gate on the way in: ask → working → results
// seamlessly. Either way the SELECT-only chokepoint (invariant 1) still applies and
// the SQL stays reviewable, editable, and re-runnable. The same review step is reused
// for the deterministic live "Pull <value> data" wrap (Inc 4) and for "Edit & re-run".
const EXAMPLES = [
  "Top customers by outstanding AR this year",
  "Monthly AP spend by supplier, last 12 months",
  "Overdue invoices over 30 days, by org",
];

type ResultsState = {
  kind: "results";
  question: string;
  sql: string;
  result: ExecuteResult;
  pullable: boolean; // false once we're already viewing a pulled detail (no nested wrap / bind-free edit)
};

// What the review step shows/edits — shared by an LLM proposal, a pull-detail wrap,
// and an "Edit & re-run".
type ReviewData = {
  question: string;
  eyebrow: string;
  sql: string;
  confidence?: Confidence;
  explanation?: string | null;
  binds?: Record<string, unknown>; // present only for pull-detail
  returnResults?: ResultsState; // a review opened from results returns here on Back
};

type AskState =
  | { kind: "idle" }
  | { kind: "proposing"; question: string } // manual: ask form shows busy
  | { kind: "working"; question: string } // auto-run: seamless full-screen loader
  | { kind: "review"; data: ReviewData }
  | { kind: "running"; data: ReviewData } // manual: review + Run spinner
  | ResultsState
  | { kind: "demo" };

type PhaseError = (StepError & { phase: "propose" | "run" }) | null;

// Sanitize any failure into the E9 shape (friendly message + error_id), never raw.
// Shares the app-wide policy: network/5xx → generic "contact IT support".
function toStepError(e: unknown): StepError {
  return friendlyError(e);
}

export function AskPage() {
  const { profileId, schemaId, autoRun, setAutoRun } = useSession();
  const [q, setQ] = useState("");
  const [state, setState] = useState<AskState>({ kind: "idle" });
  const [error, setError] = useState<PhaseError>(null);

  function reset() {
    setError(null);
    setState({ kind: "idle" });
  }

  // A review's "Back": one opened from a result returns to that result; an LLM
  // proposal returns to the ask form to edit the question.
  function back() {
    setError(null);
    if (state.kind === "review" && state.data.returnResults) setState(state.data.returnResults);
    else setState({ kind: "idle" });
  }

  // Execute a ReviewData via the SELECT-only chokepoint. `inflight` is the loading
  // state to show meanwhile (the review+spinner for a manual Run, or the seamless
  // loader for auto-run). On failure we drop to the editable review so a bad query
  // is one edit away from a re-run (E9).
  async function runData(data: ReviewData, inflight: AskState) {
    if (!profileId) return;
    setError(null);
    setState(inflight);
    try {
      const result = await execute({ sql: data.sql, profile_id: profileId, binds: data.binds });
      setState({
        kind: "results",
        question: data.question,
        sql: data.sql,
        result,
        pullable: data.binds === undefined,
      });
    } catch (e) {
      setError({ ...toStepError(e), phase: "run" });
      setState({ kind: "review", data });
    }
  }

  async function generate() {
    const question = q.trim();
    if (!question) return;
    setError(null);
    // Auto-run only when a connection is set; otherwise fall back to the review so
    // the user can pick a connection (Run shows the E10 hint).
    const auto = autoRun && !!profileId;
    setState(auto ? { kind: "working", question } : { kind: "proposing", question });
    try {
      const proposal = await nl2sql({ natural_language: question, schema_id: schemaId ?? undefined });
      const data: ReviewData = {
        question,
        eyebrow: "Review proposed SQL",
        sql: proposal.sql,
        confidence: proposal.confidence ?? null,
        explanation: proposal.explanation,
      };
      if (auto) await runData(data, { kind: "working", question });
      else setState({ kind: "review", data });
    } catch (e) {
      setError({ ...toStepError(e), phase: "propose" });
      setState({ kind: "idle" });
    }
  }

  async function run() {
    if (state.kind !== "review") return;
    await runData(state.data, { kind: "running", data: state.data });
  }

  // Decision 3 — deterministically wrap the approved SQL, scoped to the drill path,
  // and route it through the review step for re-approval before it runs live.
  function enterPullDetail(from: ResultsState, filters: PullFilter[]) {
    const { sql, binds } = buildPullDetailSql(from.sql, filters);
    const label = filters.length ? filters.map((f) => f.value).join(" · ") : "Full result";
    setError(null);
    setState({
      kind: "review",
      data: {
        question: `Live detail · ${label}`,
        eyebrow: "Review live-detail query",
        sql,
        explanation:
          "Re-runs your approved query live, scoped to this selection. Read-only — nothing runs until you approve.",
        confidence: null,
        binds,
        returnResults: from,
      },
    });
  }

  // Pull the query up from a result, edit it, and re-run (works in both modes).
  function editSql(from: ResultsState) {
    setError(null);
    setState({
      kind: "review",
      data: {
        question: from.question,
        eyebrow: "Edit & re-run SQL",
        sql: from.sql,
        explanation: "Edit the query and re-run it. Read-only — nothing runs until you approve.",
        confidence: null,
        returnResults: from,
      },
    });
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
    const s = state;
    return (
      <ResultsView
        question={s.question}
        sql={s.sql}
        result={s.result}
        onBack={reset}
        onPullDetail={s.pullable ? (filters) => enterPullDetail(s, filters) : undefined}
        onEditSql={s.pullable ? () => editSql(s) : undefined}
      />
    );
  }

  if (state.kind === "working") {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <Loader2 className="h-7 w-7 animate-spin text-brand" />
        <div className="mt-4 font-display text-[18px] font-semibold text-ink">Working on it…</div>
        <p className="mt-1.5 max-w-md truncate text-[13.5px] text-ink-muted">{state.question}</p>
        <p className="mt-0.5 text-[12px] text-ink-faint">
          Converting your question to SQL and fetching results.
        </p>
      </div>
    );
  }

  if (state.kind === "review" || state.kind === "running") {
    const { data } = state;
    return (
      <ProposedSql
        question={data.question}
        eyebrow={data.eyebrow}
        confidence={data.confidence}
        explanation={data.explanation}
        binds={data.binds}
        sql={data.sql}
        onSqlChange={(v) =>
          setState((s) => (s.kind === "review" ? { ...s, data: { ...s.data, sql: v } } : s))
        }
        onRun={run}
        onBack={back}
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
          nothing runs until you approve it{autoRun ? ", unless Auto-run is on" : ""}.
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
          <div className="flex items-center justify-between gap-3 px-2 pt-1">
            <div className="flex min-w-0 items-center gap-2.5">
              <AutoRunSwitch on={autoRun} onChange={setAutoRun} />
              <span className="truncate text-[12px] text-ink-faint">
                {autoRun ? "Converts & runs automatically · read-only" : "AI proposes · you approve · read-only"}
              </span>
            </div>
            <button
              type="button"
              onClick={generate}
              disabled={!q.trim() || busy}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity disabled:opacity-40"
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {busy ? "Working…" : autoRun ? "Ask" : "Generate SQL"}
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

// Auto-run on/off. An accessible switch (role="switch"); the choice persists in
// session context. On → asking converts + runs in the background; off → review first.
function AutoRunSwitch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Auto-run"
      onClick={() => onChange(!on)}
      title="Auto-run: convert and fetch results without the review step"
      className={`inline-flex shrink-0 items-center gap-1.5 text-[12px] font-medium ${
        on ? "text-brand" : "text-ink-faint"
      }`}
    >
      <span
        className={`relative h-[18px] w-8 rounded-full transition-colors ${
          on ? "bg-brand" : "bg-ink-faint/30"
        }`}
      >
        <span
          className={`absolute top-[3px] h-3 w-3 rounded-full bg-white shadow-sm transition-transform ${
            on ? "translate-x-[17px]" : "translate-x-[3px]"
          }`}
        />
      </span>
      <span className="inline-flex items-center gap-1">
        <Zap className="h-3.5 w-3.5" /> Auto-run
      </span>
    </button>
  );
}

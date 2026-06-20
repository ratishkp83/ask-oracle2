import { ReactNode, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Download, Layers, Loader2, Save, Send } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ColumnMeta } from "@/lib/derive/columns";
import { SqlMeta } from "@/lib/derive/sql";
import { CascadeSpec, DEFAULT_CASCADE_SPEC, resolveCascade, toPersistedSpec } from "@/lib/cascade/spec";
import { buildCascadeBundle, BundleSection, RunSql } from "@/lib/cascade/bundle";
import { renderBundleHtml } from "@/lib/cascade/renderHtml";
import { downloadHtml, slugify } from "@/lib/export";
import { createReport, emailBundle } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

type ActionStatus = { kind: "idle" | "busy" | "ok" | "error"; message?: string };

function countSections(s: BundleSection): number {
  return 1 + s.children.reduce((n, c) => n + countSections(c), 0);
}

// One toolbar action for the whole cascading-report deliverable (ADR-026): it
// builds the single-file HTML bundle once (live fan-out via `onRunSql` when a
// connection is set, else from the shown rows) and offers Download / Email / Save.
// No LLM on any path; every child query is the SELECT-only chokepoint.
export function CascadeReportDialog({
  reportSql,
  columns,
  reportRows,
  cols,
  sqlMeta,
  cascadeSpec,
  onRunSql,
  reportTitle,
  savable = false,
}: {
  reportSql: string;
  columns: string[];
  reportRows: unknown[][];
  cols: ColumnMeta[];
  sqlMeta: SqlMeta | null;
  cascadeSpec?: CascadeSpec; // saved report's spec; absent → auto-derive
  onRunSql?: RunSql; // live fresh-fetch fan-out; absent → local from the shown rows
  reportTitle: string;
  savable?: boolean; // offer "Save as report" (the ad-hoc Ask context)
}) {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<"building" | "ready" | "error">("building");
  const [html, setHtml] = useState("");
  const [summary, setSummary] = useState("");
  const [buildErr, setBuildErr] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [mode, setMode] = useState<"download" | "email" | "save">("download");

  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState(reportTitle || "Cascading report");
  const [emailStatus, setEmailStatus] = useState<ActionStatus>({ kind: "idle" });

  const [name, setName] = useState(reportTitle || "");
  const [saveStatus, setSaveStatus] = useState<ActionStatus>({ kind: "idle" });

  // Persist the *resolved* dimension order (explicit names) so a re-run reproduces
  // the same cascade regardless of auto-derive.
  function resolvedPersisted() {
    const r = resolveCascade(cascadeSpec ?? DEFAULT_CASCADE_SPEC, columns, cols, sqlMeta);
    return toPersistedSpec({
      dimensionOrder: r.dimIndices.map((i) => columns[i]),
      depth: r.dimIndices.length || 1,
      childrenPerLevel: r.childrenPerLevel,
      rowsPerChild: r.rowsPerChild,
    });
  }

  async function build() {
    setPhase("building");
    setBuildErr(null);
    setProgress(0);
    try {
      const resolved = resolveCascade(cascadeSpec ?? DEFAULT_CASCADE_SPEC, columns, cols, sqlMeta);
      const bundle = await buildCascadeBundle(
        reportSql,
        { columns, rows: reportRows },
        cols,
        sqlMeta,
        resolved,
        onRunSql,
        (n) => setProgress(n),
      );
      setHtml(renderBundleHtml(bundle, { title: reportTitle, question: reportTitle, sql: reportSql }));
      const secs = countSections(bundle.root);
      const source = onRunSql
        ? `${bundle.queries} live ${bundle.queries === 1 ? "query" : "queries"}`
        : "from the shown result";
      setSummary(`${secs} section${secs === 1 ? "" : "s"} · ${source}${bundle.truncated ? " · trimmed to size" : ""}`);
      setPhase("ready");
    } catch (e) {
      setBuildErr(errorMessage(e, "Couldn’t build the cascading report. Please try again."));
      setPhase("error");
    }
  }

  useEffect(() => {
    if (open) build();
    // Rebuild each time the dialog opens; inputs are stable for a given result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function reset() {
    setMode("download");
    setEmailStatus({ kind: "idle" });
    setSaveStatus({ kind: "idle" });
  }

  function doDownload() {
    downloadHtml(`${slugify(reportTitle) || "report"}-cascading`, html);
  }

  async function doEmail() {
    setEmailStatus({ kind: "busy" });
    try {
      const res = await emailBundle({
        to,
        cc,
        subject,
        body: "Your cascading report is attached as an HTML file.",
        html,
      });
      setEmailStatus({ kind: "ok", message: res.message });
    } catch (e) {
      setEmailStatus({ kind: "error", message: errorMessage(e, "Couldn’t send the report. Please try again.") });
    }
  }

  async function doSave() {
    setSaveStatus({ kind: "busy" });
    try {
      await createReport({ name: name.trim(), sql: reportSql, cascade: resolvedPersisted() });
      setSaveStatus({ kind: "ok", message: `Saved “${name.trim()}” as a cascading report.` });
    } catch (e) {
      setSaveStatus({ kind: "error", message: errorMessage(e, "Couldn’t save the report. Please try again.") });
    }
  }

  const recipients = to.split(/[,;\s]+/).filter(Boolean);
  const modes: Array<{ id: typeof mode; label: string }> = [
    { id: "download", label: "Download" },
    { id: "email", label: "Email" },
    ...(savable ? [{ id: "save" as const, label: "Save" }] : []),
  ];

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          title="Build a cascading report (summary → breakdowns) you can download, email, or save"
          className="inline-flex items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink hover:bg-surface-sunken"
        >
          <Layers className="h-3.5 w-3.5 text-ink-muted" /> Report
        </button>
      </DialogTrigger>
      <DialogContent className="bg-surface sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Cascading report</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            A summary that fans out into per-value breakdowns, as one self-contained HTML file.
          </DialogDescription>
        </DialogHeader>

        {phase === "building" ? (
          <div className="flex items-center gap-2.5 rounded-control bg-surface-sunken px-3 py-3 text-[13px] text-ink-muted">
            <Loader2 className="h-4 w-4 animate-spin text-brand" />
            <span>Building the report{onRunSql && progress > 0 ? ` · ${progress} queries` : ""}…</span>
          </div>
        ) : phase === "error" ? (
          <div className="space-y-3">
            <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{buildErr}</span>
            </div>
            <button onClick={build} className="rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white">
              Try again
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-[12px] text-ink-faint">{summary}</div>

            <div className="flex gap-1.5">
              {modes.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`rounded-control border px-3 py-1.5 text-[12px] font-medium ${
                    mode === m.id ? "border-brand bg-brand-weak text-brand" : "border-hairline text-ink-muted"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {mode === "download" && (
              <button
                onClick={doDownload}
                className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white"
              >
                <Download className="h-3.5 w-3.5" /> Download HTML
              </button>
            )}

            {mode === "email" &&
              (emailStatus.kind === "ok" ? (
                <div className="flex items-start gap-2 rounded-control bg-[#E7F3EC] px-3 py-2.5 text-[13px] text-gain">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{emailStatus.message}</span>
                </div>
              ) : (
                <div className="space-y-2.5">
                  <Field label="To">
                    <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@company.com" className={inputCls} />
                  </Field>
                  <Field label="Cc (optional)">
                    <input value={cc} onChange={(e) => setCc(e.target.value)} className={inputCls} />
                  </Field>
                  <Field label="Subject">
                    <input value={subject} onChange={(e) => setSubject(e.target.value)} className={inputCls} />
                  </Field>
                  {emailStatus.kind === "error" && (
                    <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{emailStatus.message}</span>
                    </div>
                  )}
                  <button
                    onClick={doEmail}
                    disabled={recipients.length === 0 || emailStatus.kind === "busy"}
                    className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
                  >
                    {emailStatus.kind === "busy" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                    {emailStatus.kind === "busy"
                      ? "Sending…"
                      : recipients.length
                        ? `Send to ${recipients.length} recipient${recipients.length > 1 ? "s" : ""}`
                        : "Send"}
                  </button>
                  <p className="text-[11px] text-ink-faint">The email is real — check the recipient.</p>
                </div>
              ))}

            {mode === "save" &&
              (saveStatus.kind === "ok" ? (
                <div className="flex items-start gap-2 rounded-control bg-[#E7F3EC] px-3 py-2.5 text-[13px] text-gain">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{saveStatus.message}</span>
                </div>
              ) : (
                <div className="space-y-2.5">
                  <Field label="Report name">
                    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. AR by region — FY26" className={inputCls} />
                  </Field>
                  <p className="text-[11px] text-ink-faint">
                    Saves the query and its cascade so you can re-run it from Reports.
                  </p>
                  {saveStatus.kind === "error" && (
                    <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{saveStatus.message}</span>
                    </div>
                  )}
                  <button
                    onClick={doSave}
                    disabled={!name.trim() || saveStatus.kind === "busy"}
                    className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
                  >
                    {saveStatus.kind === "busy" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                    Save report
                  </button>
                </div>
              ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">{label}</span>
      {children}
    </label>
  );
}

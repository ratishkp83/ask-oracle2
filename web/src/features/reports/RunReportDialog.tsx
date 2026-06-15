import { ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, ChevronDown, Code2, Database, Loader2, Play } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { getProfiles, runReport } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import type { ExecuteResult, Report, ReportParam } from "@/lib/api/schemas";
import { useSession } from "@/app/session";

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

// Coerce a raw form value to the bind shape the server expects (it re-coerces and
// applies defaults/required checks too). Blank → omitted so the server's default
// (if any) applies.
function coerce(p: ReportParam, raw: string): unknown {
  const v = raw.trim();
  if (v === "") return undefined;
  if (p.type === "number") {
    const n = Number(v);
    return Number.isFinite(n) ? n : v;
  }
  if (p.type === "list") return v.split(",").map((s) => s.trim()).filter(Boolean);
  return v; // string / date (ISO string)
}

function hasDefault(p: ReportParam): boolean {
  return p.default !== null && p.default !== undefined && p.default !== "";
}

// Run a saved report. Collects typed parameter binds (when any), confirms the
// connection target, then runs through the SELECT-only chokepoint (invariant 1)
// and hands the result up to the page, which shows the executive Results view.
export function RunReportDialog({
  report,
  onResult,
}: {
  report: Report;
  onResult: (report: Report, result: ExecuteResult) => void;
}) {
  const { profileId } = useSession();
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: getProfiles });
  const active = profiles?.find((p) => p.id === profileId) ?? null;

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  // Connection: session selection overrides; else the report's bound profile.
  const hasConnection = !!profileId || !!report.default_profile_id;
  const requiredMissing = report.parameters.some(
    (p) => p.required && !hasDefault(p) && !(form[p.name] ?? "").trim(),
  );

  const run = useMutation({
    mutationFn: () => {
      const binds: Record<string, unknown> = {};
      for (const p of report.parameters) {
        const v = coerce(p, form[p.name] ?? "");
        if (v !== undefined) binds[p.name] = v;
      }
      return runReport(report.id, {
        profile_id: profileId ?? undefined,
        binds: Object.keys(binds).length ? binds : undefined,
      });
    },
    onSuccess: (result) => {
      setOpen(false);
      onResult(report, result);
    },
  });

  function reset() {
    const init: Record<string, string> = {};
    for (const p of report.parameters) init[p.name] = p.default != null ? String(p.default) : "";
    setForm(init);
    run.reset();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) reset();
        else run.reset();
      }}
    >
      <DialogTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3 py-1.5 text-[12.5px] font-medium text-white transition-opacity hover:opacity-90">
          <Play className="h-3.5 w-3.5" /> Run
        </button>
      </DialogTrigger>
      <DialogContent className="bg-surface sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Run “{report.name}”</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            {report.parameters.length
              ? "Set the parameters, then run. Read-only — runs through the same safety chokepoint."
              : "Runs read-only through the same safety chokepoint."}
          </DialogDescription>
        </DialogHeader>

        {active ? (
          <div className="flex items-center gap-2 rounded-control bg-surface-sunken px-3 py-2 text-[12.5px] text-ink">
            <Database className="h-3.5 w-3.5 shrink-0 text-brand" />
            <span className="font-medium">{active.name}</span>
            <span className="text-ink-faint">· {active.username}@{active.host}</span>
          </div>
        ) : report.default_profile_id ? (
          <div className="flex items-center gap-2 rounded-control bg-surface-sunken px-3 py-2 text-[12.5px] text-ink-muted">
            <Database className="h-3.5 w-3.5 shrink-0 text-ink-faint" /> Runs against the report’s bound connection.
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-control bg-[#FBF3E6] px-3 py-2 text-[12.5px] text-warn">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              No active connection.{" "}
              <Link to="/connections" className="font-medium text-brand hover:underline" onClick={() => setOpen(false)}>
                Add or select one
              </Link>{" "}
              first.
            </span>
          </div>
        )}

        <details className="group rounded-control border border-hairline bg-surface-sunken/40">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-[12px] font-medium text-ink-muted">
            <Code2 className="h-3.5 w-3.5" /> View SQL
            <ChevronDown className="ml-auto h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          </summary>
          <pre className="num max-h-40 overflow-auto whitespace-pre-wrap border-t border-hairline px-3 py-2 text-[11.5px] leading-relaxed text-ink">
            {report.sql}
          </pre>
        </details>

        {report.parameters.length > 0 && (
          <div className="space-y-3">
            {report.parameters.map((p) => (
              <Field key={p.name} label={`${p.label || p.name}${p.required && !hasDefault(p) ? " *" : ""}`}>
                <input
                  type={p.type === "date" ? "date" : "text"}
                  inputMode={p.type === "number" ? "numeric" : undefined}
                  value={form[p.name] ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, [p.name]: e.target.value }))}
                  placeholder={p.type === "list" ? "comma, separated, values" : undefined}
                  className={inputCls}
                />
              </Field>
            ))}
          </div>
        )}

        {run.isError && (
          <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errorMessage(run.error)}</span>
          </div>
        )}

        <DialogFooter>
          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={!hasConnection || requiredMissing || run.isPending}
            className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
          >
            {run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {run.isPending ? "Running…" : "Run report"}
          </button>
        </DialogFooter>
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

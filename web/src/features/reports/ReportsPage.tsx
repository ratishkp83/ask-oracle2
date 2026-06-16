import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Database, FileText, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { ResultsView } from "@/components/exec/ResultsView";
import { deleteReport, execute, getProfiles, getReports, getTemplates } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import type { ExecuteResult, Report, Template } from "@/lib/api/schemas";
import { fromPersistedSpec } from "@/lib/cascade/spec";
import { useSession } from "@/app/session";
import { RunReportDialog } from "./RunReportDialog";
import { ReportEditorDialog, type ReportSeed } from "./ReportEditorDialog";

type View = { kind: "list" } | { kind: "results"; report: Report; result: ExecuteResult };
type EditorState = { open: boolean; report?: Report | null; seed?: ReportSeed | null };

// Reports (B6): saved reports — list, run (reusing the executive Results view +
// export/email), create/edit/delete, and start-from-template. Running goes through
// the same SELECT-only chokepoint as Ask (invariant 1); the report SQL is shown
// and stays reviewable in the editor.
export function ReportsPage() {
  const { profileId } = useSession();
  const { data: reports, isLoading, isError, error } = useQuery({ queryKey: ["reports"], queryFn: getReports });
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: getProfiles });
  const [view, setView] = useState<View>({ kind: "list" });
  const [editor, setEditor] = useState<EditorState>({ open: false });
  const [pickTemplate, setPickTemplate] = useState(false);

  if (view.kind === "results") {
    // A saved cascading report regenerates its bundle from the saved spec, fetching
    // fresh child slices live through the chokepoint when a connection is available.
    const runProfile = profileId ?? view.report.default_profile_id ?? undefined;
    return (
      <ResultsView
        question={view.report.name}
        sql={view.report.sql}
        result={view.result}
        onBack={() => setView({ kind: "list" })}
        cascadeSpec={view.report.cascade ? fromPersistedSpec(view.report.cascade) : undefined}
        onRunSql={
          runProfile
            ? async (sql, binds) => {
                const r = await execute({ sql, profile_id: runProfile, binds });
                return { columns: r.columns ?? [], rows: r.rows ?? [] };
              }
            : undefined
        }
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-hairline px-8 py-5">
        <div className="min-w-0">
          <h1 className="font-display text-[22px] font-semibold tracking-[-0.01em] text-ink">Reports</h1>
          <p className="mt-0.5 max-w-xl text-[13px] text-ink-muted">
            Saved queries you can run, parameterize, and share. Read-only — every run goes through the same safety
            chokepoint.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setPickTemplate(true)}
            className="inline-flex items-center gap-1.5 rounded-control border border-hairline px-3 py-2 text-[13px] font-medium text-ink-muted transition-colors hover:border-brand hover:text-ink"
          >
            <Sparkles className="h-4 w-4" /> From template
          </button>
          <button
            type="button"
            onClick={() => setEditor({ open: true, report: null, seed: null })}
            className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> New report
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        {isLoading ? (
          <ListSkeleton />
        ) : isError ? (
          <ErrorState message={errorMessage(error)} />
        ) : !reports || reports.length === 0 ? (
          <EmptyState onNew={() => setEditor({ open: true, report: null, seed: null })} />
        ) : (
          <ul className="overflow-hidden rounded-card border border-hairline bg-surface shadow-e1">
            {reports.map((r) => (
              <ReportRow
                key={r.id}
                report={r}
                boundConnection={
                  r.default_profile_id
                    ? (profiles?.find((p) => p.id === r.default_profile_id)?.name ?? "bound connection")
                    : undefined
                }
                onEdit={() => setEditor({ open: true, report: r, seed: null })}
                onResult={(report, result) => setView({ kind: "results", report, result })}
              />
            ))}
          </ul>
        )}
      </div>

      <ReportEditorDialog
        open={editor.open}
        onOpenChange={(o) => setEditor((e) => ({ ...e, open: o }))}
        report={editor.report}
        seed={editor.seed}
      />
      <TemplatePickerDialog
        open={pickTemplate}
        onOpenChange={setPickTemplate}
        onPick={(t) => {
          setPickTemplate(false);
          setEditor({
            open: true,
            report: null,
            seed: { name: t.name, description: t.description, sql: t.sql, parameters: t.parameters, template_id: t.id },
          });
        }}
      />
    </div>
  );
}

function ReportRow({
  report,
  boundConnection,
  onEdit,
  onResult,
}: {
  report: Report;
  boundConnection?: string;
  onEdit: () => void;
  onResult: (report: Report, result: ExecuteResult) => void;
}) {
  const paramCount = report.parameters.length;
  return (
    <li className="flex items-center gap-4 border-b border-hairline px-4 py-3 last:border-b-0">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] bg-brand-weak text-brand">
        <FileText className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[14px] font-semibold text-ink">{report.name}</span>
          {report.template_id && (
            <span className="shrink-0 rounded-full bg-surface-sunken px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
              template
            </span>
          )}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12px] text-ink-faint">
          {report.description && <span className="truncate">{report.description}</span>}
          {report.description && <span aria-hidden>·</span>}
          <span>
            {paramCount} {paramCount === 1 ? "parameter" : "parameters"}
          </span>
          {boundConnection && (
            <>
              <span aria-hidden>·</span>
              <span className="inline-flex items-center gap-1 truncate">
                <Database className="h-3 w-3 shrink-0" /> {boundConnection}
              </span>
            </>
          )}
        </div>
      </div>

      <RunReportDialog report={report} onResult={onResult} />
      <button
        type="button"
        onClick={onEdit}
        className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-control border border-hairline px-3 text-[12.5px] font-medium text-ink-muted transition-colors hover:border-brand hover:text-ink"
      >
        <Pencil className="h-3.5 w-3.5" /> Edit
      </button>
      <DeleteReportDialog report={report} />
    </li>
  );
}

function DeleteReportDialog({ report }: { report: Report }) {
  const qc = useQueryClient();
  return (
    <ConfirmDialog
      triggerAriaLabel={`Delete ${report.name}`}
      triggerClassName="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-hairline text-ink-faint transition-colors hover:border-loss hover:text-loss"
      triggerChildren={<Trash2 className="h-3.5 w-3.5" />}
      title="Delete report"
      description={
        <>
          Remove <span className="font-medium text-ink">{report.name}</span>? This can’t be undone.
        </>
      }
      onConfirm={() => deleteReport(report.id)}
      onConfirmed={() => qc.invalidateQueries({ queryKey: ["reports"] })}
    />
  );
}

function TemplatePickerDialog({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (template: Template) => void;
}) {
  const { data: templates, isLoading, isError, error } = useQuery({
    queryKey: ["templates"],
    queryFn: getTemplates,
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto bg-surface sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Start from a template</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            Curated EBS reference queries. Pick one to pre-fill a new report — review and adjust before running.
          </DialogDescription>
        </DialogHeader>
        {isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-card bg-surface-sunken" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState message={errorMessage(error)} />
        ) : (
          <ul className="space-y-1.5">
            {templates?.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onPick(t)}
                  className="flex w-full items-start gap-3 rounded-card border border-hairline px-3.5 py-2.5 text-left transition-colors hover:border-brand hover:bg-surface-sunken"
                >
                  <span className="mt-0.5 shrink-0 rounded-full bg-brand-weak px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-brand">
                    {t.module}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13.5px] font-semibold text-ink">{t.name}</span>
                    <span className="block text-[12px] text-ink-muted">{t.description}</span>
                  </span>
                </button>
              </li>
            ))}
            {templates && templates.length === 0 && (
              <p className="text-[13px] text-ink-muted">No templates available.</p>
            )}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-hairline bg-surface px-6 py-16 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-[11px] bg-brand-weak text-brand">
        <FileText className="h-5 w-5" />
      </div>
      <div>
        <p className="text-[15px] font-semibold text-ink">No saved reports yet</p>
        <p className="mt-1 max-w-sm text-[13px] text-ink-muted">
          Save a query as a report to run it again later — or start from a curated EBS template.
        </p>
      </div>
      <button
        type="button"
        onClick={onNew}
        className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white"
      >
        <Plus className="h-4 w-4" /> New report
      </button>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-card border border-loss/30 bg-loss/5 px-4 py-3 text-[13px] text-ink"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-loss" />
      <span>{message}</span>
    </div>
  );
}

function ListSkeleton() {
  return (
    <ul className="overflow-hidden rounded-card border border-hairline bg-surface">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex items-center gap-4 border-b border-hairline px-4 py-3.5 last:border-b-0">
          <div className="h-9 w-9 shrink-0 animate-pulse rounded-[9px] bg-surface-sunken" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-40 animate-pulse rounded bg-surface-sunken" />
            <div className="h-2.5 w-64 animate-pulse rounded bg-surface-sunken" />
          </div>
        </li>
      ))}
    </ul>
  );
}

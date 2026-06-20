import { ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2, Plus, Save, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createReport, getProfiles, getSchema, updateReport, type ReportCreateBody } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import type { Report, ReportParam } from "@/lib/api/schemas";
import { useSession } from "@/app/session";

// Foreign-key-derived lookup suggestions from the active data dictionary: for each
// FK column, a ready-to-use value-picker SELECT against the referenced table, with
// a *_NAME column chosen as the label when present.
type FkSuggestion = { label: string; sql: string };

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

export type ReportSeed = {
  name?: string;
  description?: string;
  sql?: string;
  parameters?: ReportParam[];
  template_id?: string | null;
};

const PARAM_TYPES: ReportParam["type"][] = ["string", "number", "date", "list"];

// Create or edit a saved report. SELECT/CTE only is still enforced server-side at
// run time (invariant 1) — this just stores the SQL + typed parameters. `report`
// drives an edit (PUT); otherwise it's a create (POST), optionally pre-filled from
// a template via `seed`.
export function ReportEditorDialog({
  open,
  onOpenChange,
  report,
  seed,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  report?: Report | null;
  seed?: ReportSeed | null;
}) {
  const qc = useQueryClient();
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: getProfiles });

  // The active data dictionary (if any) powers the FK-based lookup suggestions.
  const { schemaId } = useSession();
  const { data: schema } = useQuery({
    queryKey: ["schema", schemaId],
    queryFn: () => getSchema(schemaId as string),
    enabled: !!schemaId && open,
  });
  const fkSuggestions = useMemo<FkSuggestion[]>(() => {
    if (!schema) return [];
    const tables = schema.definition.tables;
    const out: FkSuggestion[] = [];
    for (const [tableName, cols] of Object.entries(tables)) {
      for (const c of cols) {
        if (!c.is_foreign_key || !c.references_table) continue;
        const refTable = c.references_table;
        const refCol = c.references_column || c.column_name;
        const labelCol = (tables[refTable] ?? []).find((rc) => /name/i.test(rc.column_name))?.column_name ?? refCol;
        out.push({
          label: `${tableName}.${c.column_name} → ${refTable}`,
          sql: `SELECT ${refCol}, ${labelCol} FROM ${refTable} ORDER BY ${labelCol}`,
        });
      }
    }
    return out;
  }, [schema]);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sql, setSql] = useState("");
  const [defaultProfileId, setDefaultProfileId] = useState("");
  const [params, setParams] = useState<ReportParam[]>([]);

  const save = useMutation({
    mutationFn: () => {
      const body: ReportCreateBody = {
        name: name.trim(),
        description: description.trim(),
        sql,
        parameters: params.map((p) => ({
          ...p,
          name: p.name.trim(),
          label: p.label.trim(),
          lookup_sql: p.lookup_sql?.trim() || null,
        })),
        default_profile_id: defaultProfileId || null,
        template_id: report?.template_id ?? seed?.template_id ?? null,
      };
      return report ? updateReport(report.id, body) : createReport(body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      onOpenChange(false);
    },
  });

  // Populate the form when the dialog opens (from the edited report or a seed).
  // Re-init keys only on `open` by design: the dialog is always closed between
  // distinct edits (the page sets editor state then opens), so report/seed never
  // change while it's already open. Exit-gate review F-4 (latent; documented).
  useEffect(() => {
    if (!open) return;
    const src = report ?? seed ?? null;
    setName(src?.name ?? "");
    setDescription(src?.description ?? "");
    setSql(src?.sql ?? "");
    setDefaultProfileId(report?.default_profile_id ?? "");
    setParams(src?.parameters ?? []);
    save.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const namesValid = params.every((p) => p.name.trim().length > 0);
  const canSave = !!name.trim() && !!sql.trim() && namesValid && !save.isPending;

  const addParam = () => setParams((ps) => [...ps, { name: "", label: "", type: "string", required: true }]);
  const removeParam = (i: number) => setParams((ps) => ps.filter((_, idx) => idx !== i));
  const patchParam = (i: number, patch: Partial<ReportParam>) =>
    setParams((ps) => ps.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto bg-surface sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">
            {report ? "Edit report" : "New report"}
          </DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            A saved SELECT query with optional parameters. It runs read-only through the safety chokepoint.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Monthly AP spend" className={inputCls} />
          </Field>
          <Field label="Description (optional)">
            <input value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls} />
          </Field>
          <Field label="SQL (SELECT / CTE only)">
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              rows={6}
              spellCheck={false}
              placeholder="SELECT ... FROM ... WHERE col = :param"
              className={`${inputCls} num resize-y`}
            />
          </Field>
          <Field label="Default connection (optional)">
            <select value={defaultProfileId} onChange={(e) => setDefaultProfileId(e.target.value)} className={inputCls}>
              <option value="">None — choose at run time</option>
              {profiles?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                Parameters (bound as :name)
              </span>
              <button
                type="button"
                onClick={addParam}
                className="inline-flex items-center gap-1 rounded-control border border-hairline px-2 py-1 text-[11.5px] font-medium text-ink-muted hover:border-brand hover:text-ink"
              >
                <Plus className="h-3 w-3" /> Add
              </button>
            </div>
            {params.length === 0 ? (
              <p className="text-[12px] text-ink-faint">No parameters — the SQL runs as-is.</p>
            ) : (
              <div className="space-y-2">
                {params.map((p, i) => (
                  <div key={i} className="space-y-1.5 rounded-control border border-hairline/70 bg-surface-sunken/30 p-2">
                    <div className="flex items-center gap-2">
                      <input
                        aria-label={`Parameter ${i + 1} name`}
                        value={p.name}
                        onChange={(e) => patchParam(i, { name: e.target.value })}
                        placeholder="name"
                        className={`${inputCls} num flex-1`}
                      />
                      <select
                        aria-label={`Parameter ${i + 1} type`}
                        value={p.type}
                        onChange={(e) => patchParam(i, { type: e.target.value as ReportParam["type"] })}
                        className={`${inputCls} w-[92px] shrink-0`}
                      >
                        {PARAM_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                      <label className="flex shrink-0 items-center gap-1 text-[11.5px] text-ink-muted">
                        <input
                          type="checkbox"
                          checked={p.required}
                          onChange={(e) => patchParam(i, { required: e.target.checked })}
                        />
                        req.
                      </label>
                      <button
                        type="button"
                        aria-label={`Remove parameter ${i + 1}`}
                        onClick={() => removeParam(i)}
                        className="shrink-0 rounded-control border border-hairline p-1.5 text-ink-faint hover:border-loss hover:text-loss"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {/* Optional value picker: a SELECT (value [, label]) that drives a live
                        dropdown at run time. "Suggest…" fills it from a foreign key in the
                        active data dictionary. */}
                    <div className="flex items-center gap-2">
                      <input
                        aria-label={`Parameter ${i + 1} value list SQL`}
                        value={p.lookup_sql ?? ""}
                        onChange={(e) => patchParam(i, { lookup_sql: e.target.value })}
                        placeholder="Value picker SQL (optional) — SELECT value, label FROM …"
                        className={`${inputCls} num flex-1`}
                      />
                      {fkSuggestions.length > 0 && (
                        <select
                          aria-label={`Parameter ${i + 1} suggest value picker`}
                          value=""
                          onChange={(e) => {
                            const s = fkSuggestions[Number(e.target.value)];
                            if (s) patchParam(i, { lookup_sql: s.sql });
                          }}
                          title="Suggest from a foreign key in the active schema"
                          className={`${inputCls} w-[132px] shrink-0`}
                        >
                          <option value="">Suggest…</option>
                          {fkSuggestions.map((s, idx) => (
                            <option key={idx} value={idx}>
                              {s.label}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {save.isError && (
            <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{errorMessage(save.error)}</span>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-control border border-hairline px-4 py-2 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={!canSave}
            className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
          >
            {save.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            {save.isPending ? "Saving…" : report ? "Save changes" : "Create report"}
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

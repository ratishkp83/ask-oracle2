import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  BookText,
  CheckCircle2,
  ChevronRight,
  Database,
  KeyRound,
  Lightbulb,
  Link2,
  ShieldCheck,
  Table2,
  Trash2,
} from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  deleteSchema,
  getPack,
  getPacks,
  getSchema,
  getSchemaAdvisory,
  getSchemaReadiness,
  getSchemas,
} from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import type { Readiness, SchemaRecord, SchemaSummary, Suggestion } from "@/lib/api/schemas";
import { IntrospectDialog } from "./IntrospectDialog";

type SchemaColumns = SchemaRecord["definition"]["tables"][string];

type Selected = { kind: "schema"; id: string } | { kind: "pack"; module: string };

// Data Dictionary (B6): browse saved schemas (with table/column detail) and the
// curated EBS metadata packs. Read-only metadata only — names, types, PK/FK,
// joins, glossary; never row data (invariant 3). A live introspect (E11) lives in
// IntrospectDialog. Master-detail: the rail and the detail pane each scroll; the
// frame never does (CXO single-viewport rule).
export function DataDictionaryPage() {
  const schemasQ = useQuery({ queryKey: ["schemas"], queryFn: getSchemas });
  const packsQ = useQuery({ queryKey: ["packs"], queryFn: getPacks });
  const [sel, setSel] = useState<Selected | null>(null);

  const schemas = schemasQ.data;
  const packs = packsQ.data;

  // Effective selection: a still-valid explicit pick (survives a deleted schema),
  // else the first schema, else the first pack.
  let effective: Selected | null = null;
  if (sel?.kind === "schema" && schemas?.some((s) => s.id === sel.id)) effective = sel;
  else if (sel?.kind === "pack" && packs?.some((p) => p.module === sel.module)) effective = sel;
  else if (schemas && schemas.length) effective = { kind: "schema", id: schemas[0].id };
  else if (packs && packs.length) effective = { kind: "pack", module: packs[0].module };

  const loading = schemasQ.isLoading || packsQ.isLoading;

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-hairline px-8 py-5">
        <div className="min-w-0">
          <h1 className="font-display text-[22px] font-semibold tracking-[-0.01em] text-ink">Data dictionary</h1>
          <p className="mt-0.5 max-w-xl text-[13px] text-ink-muted">
            Browse saved schemas and the curated EBS module packs (GL · AP · AR · PO · OM). Metadata only — table and
            column names, never row data.
          </p>
        </div>
        <IntrospectDialog />
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-[300px] shrink-0 overflow-y-auto border-r border-hairline px-3 py-4">
          {loading ? (
            <RailSkeleton />
          ) : (
            <>
              <RailGroup label="Saved schemas">
                {schemas && schemas.length > 0 ? (
                  schemas.map((s) => (
                    <SchemaRailItem
                      key={s.id}
                      schema={s}
                      active={effective?.kind === "schema" && effective.id === s.id}
                      onClick={() => setSel({ kind: "schema", id: s.id })}
                    />
                  ))
                ) : (
                  <p className="px-2 py-1.5 text-[12px] text-ink-faint">None yet — read one from the database.</p>
                )}
              </RailGroup>

              <RailGroup label="EBS packs">
                {packs && packs.length > 0 ? (
                  packs.map((p) => {
                    const active = effective?.kind === "pack" && effective.module === p.module;
                    return (
                    <button
                      key={p.module}
                      type="button"
                      onClick={() => setSel({ kind: "pack", module: p.module })}
                      aria-current={active ? "true" : undefined}
                      className={railItemCls(active)}
                    >
                      <BookText className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate font-medium">{p.name}</span>
                        <span className="truncate text-[11px] text-ink-faint">
                          {p.module} · {p.tables.length} {p.tables.length === 1 ? "table" : "tables"}
                        </span>
                      </span>
                    </button>
                    );
                  })
                ) : (
                  <p className="px-2 py-1.5 text-[12px] text-ink-faint">No packs available.</p>
                )}
              </RailGroup>
            </>
          )}
        </aside>

        <section className="min-w-0 flex-1 overflow-y-auto px-8 py-6">
          {!effective ? (
            <EmptyDetail />
          ) : effective.kind === "schema" ? (
            <SchemaDetail id={effective.id} />
          ) : (
            <PackDetail module={effective.module} />
          )}
        </section>
      </div>
    </div>
  );
}

// --- Rail bits --------------------------------------------------------------
function railItemCls(active: boolean) {
  return `flex w-full items-center gap-2 rounded-control px-2 py-1.5 text-left text-[12.5px] transition-colors ${
    active ? "bg-brand-weak text-brand" : "text-ink hover:bg-surface-sunken"
  }`;
}

function RailGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-faint">{label}</div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function SchemaRailItem({
  schema,
  active,
  onClick,
}: {
  schema: SchemaSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "true" : undefined}
      className={railItemCls(active)}
    >
      <Database className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
      <span className="flex min-w-0 flex-col">
        <span className="truncate font-medium">{schema.name}</span>
        <span className="truncate text-[11px] text-ink-faint">
          {schema.table_count} {schema.table_count === 1 ? "table" : "tables"} · {sourceLabel(schema.source)}
        </span>
      </span>
    </button>
  );
}

// --- Schema detail ----------------------------------------------------------
function SchemaDetail({ id }: { id: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["schema", id],
    queryFn: () => getSchema(id),
  });

  if (isLoading) return <DetailSkeleton />;
  if (isError || !data) return <ErrorBox message={errorMessage(error)} />;

  const tableNames = Object.keys(data.definition.tables).sort();
  const rels = data.definition.relationships;

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-[19px] font-semibold text-ink">{data.name}</h2>
            <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-muted">
              {sourceLabel(data.source)}
            </span>
          </div>
          <p className="mt-0.5 text-[12.5px] text-ink-faint">
            {tableNames.length} {tableNames.length === 1 ? "table" : "tables"} · {rels.length} relationship
            {rels.length === 1 ? "" : "s"}
          </p>
        </div>
        <DeleteSchemaDialog id={data.id} name={data.name} />
      </div>

      {data.source === "introspection" && <ReadinessBanner id={id} />}

      <div className="mt-5 space-y-2">
        {tableNames.map((t) => (
          <TableCard key={t} name={t} columns={data.definition.tables[t]} />
        ))}
        {tableNames.length === 0 && <p className="text-[13px] text-ink-muted">This dictionary has no tables.</p>}
      </div>

      {data.source === "introspection" && <AdvisorySection id={id} />}
    </div>
  );
}

// --- Readiness gate (D-L) + Optimization Advisory (D-K) ---------------------
function CheckStatusIcon({ status }: { status: string }) {
  if (status === "ok") return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-brand" aria-label="ready" />;
  if (status === "acknowledged")
    return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-label="acknowledged" />;
  if (status === "unavailable")
    return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-label="unavailable" />;
  return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warn" aria-label="missing" />;
}

function ReadinessBanner({ id }: { id: string }) {
  const { data } = useQuery<Readiness>({
    queryKey: ["schema-readiness", id],
    queryFn: () => getSchemaReadiness(id),
  });
  if (!data) return null;
  const tone =
    data.state === "ready"
      ? { box: "border-brand/30 bg-brand-weak", icon: <ShieldCheck className="h-4 w-4 text-brand" />, text: "Optimized — ready for CXO use" }
      : data.state === "incomplete"
        ? { box: "border-loss/30 bg-loss/5", icon: <AlertCircle className="h-4 w-4 text-loss" />, text: "Setup incomplete" }
        : { box: "border-warn/30 bg-warn/5", icon: <AlertTriangle className="h-4 w-4 text-warn" />, text: "Not optimized — accuracy/performance may suffer" };
  const okCount = data.checklist.filter((c) => c.status === "ok" || c.status === "acknowledged").length;
  return (
    <details className={`group mt-4 overflow-hidden rounded-card border ${tone.box}`}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-[13px] font-medium text-ink">
        {tone.icon}
        <span>{tone.text}</span>
        <span className="ml-auto text-[11px] font-normal text-ink-faint">
          {okCount}/{data.checklist.length} checks · {data.enforcement}-block
        </span>
        <ChevronRight className="h-3.5 w-3.5 text-ink-faint transition-transform group-open:rotate-90" />
      </summary>
      <ul className="border-t border-hairline/60 bg-surface/70">
        {data.checklist.map((c) => (
          <li key={c.key} className="flex items-center gap-2 px-3.5 py-1.5 text-[12.5px]">
            <CheckStatusIcon status={c.status} />
            <span className="text-ink">{c.label}</span>
            {c.detail && <span className="ml-auto truncate text-[11px] text-ink-faint">{c.detail}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function AdvisorySection({ id }: { id: string }) {
  const { data } = useQuery<Suggestion[]>({
    queryKey: ["schema-advisory", id],
    queryFn: () => getSchemaAdvisory(id),
  });
  if (!data || data.length === 0) return null;
  return (
    <div className="mt-6">
      <div className="mb-2 flex items-center gap-2">
        <Lightbulb className="h-3.5 w-3.5 text-warn" />
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Optimization advisory</h3>
        <span className="text-[11px] text-ink-faint">advise-only — share with your DBA; the app never runs DDL</span>
      </div>
      <div className="space-y-2">
        {data.map((s, i) => (
          <SuggestionCard key={`${s.kind}-${s.target}-${i}`} s={s} />
        ))}
      </div>
    </div>
  );
}

function SuggestionCard({ s }: { s: Suggestion }) {
  const sev = s.severity === "high" ? "text-loss" : s.severity === "medium" ? "text-warn" : "text-ink-faint";
  return (
    <div className="rounded-card border border-hairline bg-surface px-3.5 py-3">
      <div className="flex items-center gap-2">
        <span className={`text-[10px] font-semibold uppercase tracking-[0.06em] ${sev}`}>{s.severity}</span>
        <span className="text-[13px] font-semibold text-ink">{s.target}</span>
      </div>
      <p className="mt-1 text-[12.5px] text-ink-muted">{s.rationale}</p>
      <pre className="num mt-2 overflow-x-auto rounded-control bg-surface-sunken px-2.5 py-1.5 text-[11.5px] text-ink">
        {s.ddl_candidate}
      </pre>
      <p className="mt-1.5 text-[11px] text-ink-faint">Tradeoff: {s.tradeoff}</p>
    </div>
  );
}

function TableCard({ name, columns }: { name: string; columns: SchemaColumns }) {
  return (
    <details className="group overflow-hidden rounded-card border border-hairline bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3.5 py-2.5 text-[13.5px] font-medium text-ink hover:bg-surface-sunken">
        <ChevronRight className="h-3.5 w-3.5 text-ink-faint transition-transform group-open:rotate-90" />
        <Table2 className="h-3.5 w-3.5 text-brand" />
        <span className="font-semibold">{name}</span>
        <span className="ml-auto text-[11px] text-ink-faint">
          {columns.length} {columns.length === 1 ? "column" : "columns"}
        </span>
      </summary>
      <ul className="border-t border-hairline">
        {columns.map((c) => (
          <li
            key={c.column_name}
            className="flex items-center gap-2 px-3.5 py-1.5 text-[12.5px] text-ink-muted odd:bg-surface-sunken/40"
          >
            {c.is_primary_key ? (
              <KeyRound className="h-3 w-3 shrink-0 text-warn" aria-label="Primary key" />
            ) : c.is_foreign_key ? (
              <Link2 className="h-3 w-3 shrink-0 text-brand" aria-label="Foreign key" />
            ) : (
              <span className="h-3 w-3 shrink-0" />
            )}
            <span className="font-medium text-ink">{c.column_name}</span>
            {c.data_type && <span className="text-ink-faint">{c.data_type}</span>}
            {c.is_foreign_key && c.references_table && (
              <span className="ml-auto truncate text-[11px] text-ink-faint">
                → {c.references_table}
                {c.references_column ? `.${c.references_column}` : ""}
              </span>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DeleteSchemaDialog({ id, name }: { id: string; name: string }) {
  const qc = useQueryClient();
  return (
    <ConfirmDialog
      triggerAriaLabel={`Delete ${name}`}
      triggerClassName="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-control border border-hairline px-3 text-[12.5px] font-medium text-ink-faint transition-colors hover:border-loss hover:text-loss"
      triggerChildren={
        <>
          <Trash2 className="h-3.5 w-3.5" /> Delete
        </>
      }
      title="Delete schema"
      description={
        <>
          Remove the dictionary <span className="font-medium text-ink">{name}</span>? Questions will lose this schema
          as NL→SQL context until it is read again.
        </>
      }
      onConfirm={() => deleteSchema(id)}
      onConfirmed={() => qc.invalidateQueries({ queryKey: ["schemas"] })}
    />
  );
}

// --- EBS pack detail --------------------------------------------------------
function PackDetail({ module }: { module: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["pack", module],
    queryFn: () => getPack(module),
  });

  if (isLoading) return <DetailSkeleton />;
  if (isError || !data) return <ErrorBox message={errorMessage(error)} />;

  return (
    <div>
      <div className="flex items-center gap-2">
        <h2 className="font-display text-[19px] font-semibold text-ink">{data.name}</h2>
        <span className="rounded-full bg-brand-weak px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-brand">
          {data.module}
        </span>
      </div>
      <p className="mt-0.5 text-[12.5px] text-ink-faint">
        Curated EBS R12/12.2 metadata · {data.tables.length} tables · {data.glossary.length} glossary terms
      </p>

      <div className="mt-5 space-y-2">
        {data.tables.map((t) => (
          <div key={t.table} className="rounded-card border border-hairline bg-surface px-3.5 py-3">
            <div className="flex items-center gap-2">
              <Table2 className="h-3.5 w-3.5 text-brand" />
              <span className="text-[13.5px] font-semibold text-ink">{t.table}</span>
            </div>
            <p className="mt-1 text-[12.5px] text-ink-muted">{t.description}</p>
            {t.key_columns.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {t.key_columns.map((k) => (
                  <span
                    key={k}
                    className="rounded-full bg-surface-sunken px-2 py-0.5 text-[11px] font-medium text-ink-muted"
                  >
                    {k}
                  </span>
                ))}
              </div>
            )}
            {t.joins.length > 0 && (
              <ul className="mt-2 space-y-0.5">
                {t.joins.map((j) => (
                  <li key={j} className="flex items-center gap-1.5 text-[11.5px] text-ink-faint">
                    <Link2 className="h-3 w-3 shrink-0" /> <span className="num">{j}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      {data.glossary.length > 0 && (
        <div className="mt-6">
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">Glossary</h3>
          <div className="overflow-hidden rounded-card border border-hairline bg-surface">
            {data.glossary.map((g, i) => (
              <div
                key={`${g.term}-${i}`}
                className="flex items-baseline gap-3 border-b border-hairline px-3.5 py-2 text-[12.5px] last:border-b-0 odd:bg-surface-sunken/40"
              >
                <span className="w-40 shrink-0 font-medium text-ink">{g.term}</span>
                <span className="text-ink-muted">
                  {g.table}
                  {g.column ? `.${g.column}` : ""}
                  {g.note ? <span className="text-ink-faint"> — {g.note}</span> : null}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Shared bits ------------------------------------------------------------
// Plain-language label for a saved schema's origin. The stored `source` enum
// ("introspection"/"upload") stays a server contract; this is display only (ITM-034).
function sourceLabel(source: string): string {
  if (source === "introspection") return "From database";
  if (source === "upload") return "Uploaded";
  return source;
}

function EmptyDetail() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <BookText className="h-6 w-6 text-ink-faint" />
      <p className="text-[14px] font-semibold text-ink">Nothing to show yet</p>
      <p className="max-w-sm text-[13px] text-ink-muted">Read a schema from the database to build your first data dictionary.</p>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
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

function RailSkeleton() {
  return (
    <div className="space-y-2 px-2">
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="h-8 animate-pulse rounded-control bg-surface-sunken" />
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-5 w-48 animate-pulse rounded bg-surface-sunken" />
      <div className="h-10 animate-pulse rounded-card bg-surface-sunken" />
      <div className="h-10 animate-pulse rounded-card bg-surface-sunken" />
    </div>
  );
}

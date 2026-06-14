import { ReactNode, useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Download, FileSpreadsheet, Loader2, SearchX } from "lucide-react";
import { ExecuteResult } from "@/lib/api/schemas";
import { ApiError } from "@/lib/api/client";
import { downloadXlsx } from "@/lib/api/endpoints";
import { classifyColumns, ColumnMeta } from "@/lib/derive/columns";
import { parseSelectMeta } from "@/lib/derive/sql";
import { DrillLevel, dimensionOrder, filterRows } from "@/lib/derive/cascade";
import { PullFilter } from "@/lib/derive/pullDetail";
import { deriveKpis } from "@/lib/derive/kpis";
import { pickChart } from "@/lib/derive/chart";
import { downloadCsv, slugify } from "@/lib/export";
import { formatCompact, formatNumber, formatPercent, humanize, toNumber } from "@/lib/format";
import { SummaryBand } from "./SummaryBand";
import { KpiCard } from "./KpiCard";
import { DriverChart } from "./DriverChart";
import { ResultGrid } from "./ResultGrid";
import { EmailDialog } from "./EmailDialog";

interface LeafContext {
  filters: PullFilter[]; // the active drill path, outermost → deepest
  onPullQuery?: (q: string) => void; // demo: seed a fresh question
  onPullDetail?: (filters: PullFilter[]) => void; // live: wrap the approved SQL (B5b-3)
}

// The executive results hierarchy (B-6) with multi-level cascading drill-down:
// click a bar to push the next dimension onto a drill stack; the whole view
// (KPIs + breakdown chart + grid) re-scopes to the active filters at every level,
// descending in SQL GROUP BY order. A breadcrumb walks back up. When a scope has
// no further breakdown (deepest dimension or a single record) the chart band
// becomes a "pull live detail" prompt. All derivation stays local/deterministic.
export function ResultsView({
  question,
  sql,
  result,
  onBack,
  onPullQuery,
  onPullDetail,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
  onBack?: () => void;
  onPullQuery?: (q: string) => void;
  onPullDetail?: (filters: PullFilter[]) => void;
}) {
  // The proposed SQL drives classification (GROUP BY → dimensions, aggregate
  // funcs → measures + their exact aggregation) and the cascade order; the name
  // heuristics are the fallback. Parsed once and reused across drill scopes.
  const sqlMeta = useMemo(() => parseSelectMeta(sql), [sql]);
  const cols = useMemo(
    () => classifyColumns(result.columns, result.rows, sqlMeta),
    [result, sqlMeta],
  );
  const order = useMemo(() => dimensionOrder(cols, sqlMeta), [cols, sqlMeta]);
  const [stack, setStack] = useState<DrillLevel[]>([]);
  const rows = useMemo(() => filterRows(result.rows, stack), [result.rows, stack]);
  const push = (dimIndex: number, value: string) => setStack((s) => [...s, { dimIndex, value }]);

  // E1 — empty result: a calm "no rows" state with the SQL disclosure and a way
  // to refine. Never the bare grid; derivation already returns []/null for 0 rows.
  if (result.rows.length === 0) {
    return (
      <EmptyResult
        question={question}
        sql={sql}
        result={result}
        onRefine={onPullQuery ? () => onPullQuery(question) : onBack}
      />
    );
  }

  // E2 — single value (1×1): promote the one figure to a hero rather than a 1-cell grid.
  if (result.columns.length === 1 && result.rows.length === 1) {
    return <HeroResult question={question} sql={sql} result={result} col={cols[0]} onBack={onBack} />;
  }

  if (stack.length > 0) {
    const last = stack[stack.length - 1];
    const filters = stack.map((d) => ({ column: result.columns[d.dimIndex], value: d.value }));
    const header = (
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div className="min-w-0">
          <Breadcrumb columns={result.columns} stack={stack} onJump={(n) => setStack(stack.slice(0, n))} />
          <div className="num mt-1.5 text-[12.5px] text-ink-muted">
            {rows.length.toLocaleString()} of {result.row_count.toLocaleString()} rows
          </div>
        </div>
        {onBack && <NewQuestionButton onBack={onBack} />}
      </div>
    );
    return (
      <ResultScope
        columns={result.columns}
        rows={rows}
        cols={cols}
        order={order}
        excludeChartDims={stack.map((d) => d.dimIndex)}
        header={header}
        filename={`${slugify(question)}-${slugify(last.value)}`}
        subject={`${last.value} — ${question}`}
        onDrill={push}
        leaf={{ filters, onPullQuery, onPullDetail }}
      />
    );
  }

  const header = (
    <div className="flex shrink-0 items-start justify-between gap-4">
      <SummaryBand question={question} sql={sql} result={result} />
      {onBack && <NewQuestionButton onBack={onBack} />}
    </div>
  );
  return (
    <ResultScope
      columns={result.columns}
      rows={result.rows}
      cols={cols}
      order={order}
      excludeChartDims={[]}
      header={header}
      filename={slugify(question) || "result"}
      subject={question}
      onDrill={push}
    />
  );
}

function ResultScope({
  columns,
  rows,
  cols,
  order,
  excludeChartDims,
  header,
  filename,
  subject,
  onDrill,
  leaf,
}: {
  columns: string[];
  rows: unknown[][];
  cols: ColumnMeta[];
  order: number[];
  excludeChartDims: number[];
  header: ReactNode;
  filename: string;
  subject: string;
  onDrill: (dimIndex: number, value: string) => void;
  leaf?: LeafContext;
}) {
  const kpis = useMemo(() => deriveKpis(rows, cols), [rows, cols]);
  const chart = useMemo(
    () => pickChart(rows, cols, excludeChartDims, order),
    [rows, cols, excludeChartDims, order],
  );

  const [xlsxBusy, setXlsxBusy] = useState(false);
  const [exportErr, setExportErr] = useState<string | null>(null);

  async function exportXlsx() {
    setExportErr(null);
    setXlsxBusy(true);
    try {
      await downloadXlsx({ columns, rows, filename });
    } catch (e) {
      setExportErr(e instanceof ApiError ? e.message : "Excel export failed.");
    } finally {
      setXlsxBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3.5 px-6 py-5">
      {header}

      {kpis.length > 0 && (
        <div
          className="grid shrink-0 gap-3"
          style={{ gridTemplateColumns: `repeat(${Math.min(kpis.length, 4)}, minmax(0, 1fr))` }}
        >
          {kpis.map((k) => (
            <KpiCard key={k.label} kpi={k} />
          ))}
        </div>
      )}

      {chart ? (
        <div className="shrink-0">
          <DriverChart spec={chart} onBarClick={(label) => onDrill(chart.dimensionIndex, label)} />
        </div>
      ) : leaf ? (
        <NoBreakdown leaf={leaf} />
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-card border border-hairline bg-surface">
        <div className="flex shrink-0 items-center justify-between border-b border-hairline px-3.5 py-2.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
            Detail · {rows.length.toLocaleString()} rows
          </span>
          <div className="flex items-center gap-2">
            {exportErr && <span className="text-[11.5px] text-loss">{exportErr}</span>}
            <button
              type="button"
              onClick={() => downloadCsv(filename, columns, rows)}
              className="inline-flex items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink hover:bg-surface-sunken"
            >
              <Download className="h-3.5 w-3.5 text-ink-muted" /> CSV
            </button>
            <button
              type="button"
              onClick={exportXlsx}
              disabled={xlsxBusy}
              className="inline-flex items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink hover:bg-surface-sunken disabled:opacity-50"
            >
              {xlsxBusy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-muted" />
              ) : (
                <FileSpreadsheet className="h-3.5 w-3.5 text-ink-muted" />
              )}
              Excel
            </button>
            <EmailDialog question={subject} columns={columns} rows={rows} filename={filename} />
          </div>
        </div>
        <div className="min-h-0 flex-1">
          <ResultGrid columns={columns} rows={rows} cols={cols} />
        </div>
      </div>
    </div>
  );
}

// Cascade trail: Report › Dimension · Value › … Each crumb but the last jumps
// back to that depth; the last is the current scope.
function Breadcrumb({
  columns,
  stack,
  onJump,
}: {
  columns: string[];
  stack: DrillLevel[];
  onJump: (depth: number) => void;
}) {
  return (
    <nav className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-[13px]">
      <button
        type="button"
        onClick={() => onJump(0)}
        className="inline-flex items-center gap-1 font-medium text-ink-faint hover:text-ink-muted"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Report
      </button>
      {stack.map((d, i) => {
        const isLast = i === stack.length - 1;
        const crumb = (
          <span className="inline-flex items-baseline gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
              {humanize(columns[d.dimIndex])}
            </span>
            <span className={isLast ? "font-semibold text-ink" : "text-ink-muted"}>{d.value}</span>
          </span>
        );
        return (
          <span key={i} className="inline-flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-faint" />
            {isLast ? (
              crumb
            ) : (
              <button type="button" onClick={() => onJump(i + 1)} className="hover:text-ink">
                {crumb}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function NewQuestionButton({ onBack }: { onBack: () => void }) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="inline-flex shrink-0 items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-surface-sunken"
    >
      <ArrowLeft className="h-3.5 w-3.5" /> New question
    </button>
  );
}

function EmptyResult({
  question,
  sql,
  result,
  onRefine,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
  onRefine?: () => void;
}) {
  return (
    <div className="flex h-full flex-col gap-3.5 px-6 py-5">
      <SummaryBand question={question} sql={sql} result={result} />
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
          <SearchX className="h-5 w-5" />
        </div>
        <div className="mt-3 font-display text-[18px] font-semibold text-ink">No rows matched</div>
        <div className="mt-1.5 max-w-md text-[13px] leading-relaxed text-ink-muted">
          The query ran successfully but returned no rows. Open “View SQL” above to check the
          filters, then refine your question.
        </div>
        {onRefine && (
          <button
            type="button"
            onClick={onRefine}
            className="mt-4 inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[12.5px] font-medium text-white"
          >
            Refine the question
          </button>
        )}
      </div>
    </div>
  );
}

// Format the single figure for the 1×1 hero, honouring inferred currency/percent.
function heroValue(v: unknown, c: ColumnMeta): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = toNumber(v);
  if (Number.isFinite(n)) {
    if (c.type === "percent") return formatPercent(n);
    if (c.type === "currency") return formatCompact(n, true);
    if (c.numericAligned) return formatNumber(n);
  }
  return String(v);
}

function HeroResult({
  question,
  sql,
  result,
  col,
  onBack,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
  col: ColumnMeta;
  onBack?: () => void;
}) {
  return (
    <div className="flex h-full flex-col gap-3.5 px-6 py-5">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <SummaryBand question={question} sql={sql} result={result} />
        {onBack && <NewQuestionButton onBack={onBack} />}
      </div>
      <div className="flex flex-1 flex-col items-center justify-center">
        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
          {humanize(col.name)}
        </div>
        <div className="num mt-2 font-display text-[64px] font-semibold leading-none tracking-[-0.02em] text-ink">
          {heroValue(result.rows[0][0], col)}
        </div>
      </div>
    </div>
  );
}

// Leaf of the cascade: no further breakdown for the deepest value. Offer to pull
// its live detail — wired to the approved-SQL wrap in live mode (B5b-3), or to a
// fresh question in the no-DB demo.
function NoBreakdown({ leaf }: { leaf: LeafContext }) {
  const value = leaf.filters[leaf.filters.length - 1]?.value ?? "";
  const canPull = !!leaf.onPullDetail || !!leaf.onPullQuery;
  const pull = () => {
    if (leaf.onPullDetail) leaf.onPullDetail(leaf.filters);
    else leaf.onPullQuery?.(`Show all detail for ${value}`);
  };
  return (
    <div className="shrink-0 rounded-card border border-hairline bg-surface px-4 py-5 text-center">
      <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
        <SearchX className="h-4 w-4" />
      </div>
      <div className="mt-2 text-[13.5px] font-medium text-ink">
        No further breakdown for “{value}” in this result
      </div>
      <div className="mt-1 text-[12.5px] text-ink-muted">
        This is the deepest level for {value}. Pull its full detail live from the database.
      </div>
      <button
        type="button"
        onClick={pull}
        disabled={!canPull}
        className="mt-3 inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[12.5px] font-medium text-white disabled:opacity-50"
      >
        Pull {value} data →
      </button>
    </div>
  );
}

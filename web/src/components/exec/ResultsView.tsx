import { ReactNode, useMemo, useState } from "react";
import { ArrowLeft, ChevronRight, Download, FileSpreadsheet, Loader2, SearchX } from "lucide-react";
import { ExecuteResult } from "@/lib/api/schemas";
import { ApiError } from "@/lib/api/client";
import { downloadXlsx } from "@/lib/api/endpoints";
import { classifyColumns, ColumnMeta } from "@/lib/derive/columns";
import { parseSelectMeta } from "@/lib/derive/sql";
import { deriveKpis } from "@/lib/derive/kpis";
import { pickChart } from "@/lib/derive/chart";
import { downloadCsv, slugify } from "@/lib/export";
import { formatCompact, formatNumber, formatPercent, humanize, toNumber } from "@/lib/format";
import { SummaryBand } from "./SummaryBand";
import { KpiCard } from "./KpiCard";
import { DriverChart } from "./DriverChart";
import { ResultGrid } from "./ResultGrid";
import { EmailDialog } from "./EmailDialog";

interface Drill {
  dimIndex: number;
  value: string;
}

// The executive results hierarchy (B-6) with one-level drill-down: click a bar
// to scope the whole view (KPIs + breakdown chart + grid) to that value; Back
// returns to the report. If a value has no further breakdown in the result, the
// chart band becomes a "pull live detail" prompt. All derivation stays local.
export function ResultsView({
  question,
  sql,
  result,
  onBack,
  onPullQuery,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
  onBack?: () => void;
  onPullQuery?: (q: string) => void;
}) {
  // The proposed SQL drives classification (GROUP BY → dimensions, aggregate
  // funcs → measures + their exact aggregation); the name heuristics are the
  // fallback. Parsed once and reused across drill scopes (same columns/SQL).
  const sqlMeta = useMemo(() => parseSelectMeta(sql), [sql]);
  const cols = useMemo(
    () => classifyColumns(result.columns, result.rows, sqlMeta),
    [result, sqlMeta],
  );
  const [drill, setDrill] = useState<Drill | null>(null);

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

  if (drill) {
    const dimName = result.columns[drill.dimIndex];
    const rows = result.rows.filter((r) => String(r[drill.dimIndex]) === drill.value);
    const header = (
      <div className="shrink-0">
        <button
          type="button"
          onClick={() => setDrill(null)}
          className="mb-1.5 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint hover:text-ink-muted"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to report
        </button>
        <div className="flex items-center gap-1.5 font-display text-[21px] font-semibold leading-tight tracking-[-0.015em] text-ink">
          <span className="text-ink-faint">{humanize(dimName)}</span>
          <ChevronRight className="h-4 w-4 text-ink-faint" />
          <span>{drill.value}</span>
        </div>
        <div className="num mt-1 text-[12.5px] text-ink-muted">
          {rows.length} of {result.row_count.toLocaleString()} rows
        </div>
      </div>
    );
    return (
      <ResultScope
        columns={result.columns}
        rows={rows}
        cols={cols}
        header={header}
        filename={`${slugify(question)}-${slugify(drill.value)}`}
        subject={`${drill.value} — ${question}`}
        excludeChartDim={drill.dimIndex}
        drillContext={{ value: drill.value, onPull: onPullQuery }}
      />
    );
  }

  const header = (
    <div className="flex shrink-0 items-start justify-between gap-4">
      <SummaryBand question={question} sql={sql} result={result} />
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-surface-sunken"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> New question
        </button>
      )}
    </div>
  );
  return (
    <ResultScope
      columns={result.columns}
      rows={result.rows}
      cols={cols}
      header={header}
      filename={slugify(question) || "result"}
      subject={question}
      onDrill={(dimIndex, value) => setDrill({ dimIndex, value })}
    />
  );
}

function ResultScope({
  columns,
  rows,
  cols,
  header,
  filename,
  subject,
  excludeChartDim,
  onDrill,
  drillContext,
}: {
  columns: string[];
  rows: unknown[][];
  cols: ColumnMeta[];
  header: ReactNode;
  filename: string;
  subject: string;
  excludeChartDim?: number;
  onDrill?: (dimIndex: number, value: string) => void;
  drillContext?: { value: string; onPull?: (q: string) => void };
}) {
  const kpis = useMemo(() => deriveKpis(rows, cols), [rows, cols]);
  const chart = useMemo(
    () => pickChart(rows, cols, excludeChartDim != null ? [excludeChartDim] : []),
    [rows, cols, excludeChartDim],
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
          <DriverChart
            spec={chart}
            onBarClick={onDrill ? (label) => onDrill(chart.dimensionIndex, label) : undefined}
          />
        </div>
      ) : drillContext ? (
        <NoBreakdown value={drillContext.value} onPull={drillContext.onPull} />
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
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-surface-sunken"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> New question
          </button>
        )}
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

function NoBreakdown({ value, onPull }: { value: string; onPull?: (q: string) => void }) {
  return (
    <div className="shrink-0 rounded-card border border-hairline bg-surface px-4 py-5 text-center">
      <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
        <SearchX className="h-4 w-4" />
      </div>
      <div className="mt-2 text-[13.5px] font-medium text-ink">No further breakdown for “{value}” in this result</div>
      <div className="mt-1 text-[12.5px] text-ink-muted">
        This report holds a single record for {value}. Pull its full detail from the database.
      </div>
      <button
        type="button"
        onClick={() => onPull?.(`Show all detail for ${value}`)}
        disabled={!onPull}
        className="mt-3 inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[12.5px] font-medium text-white disabled:opacity-50"
      >
        Pull {value} data →
      </button>
    </div>
  );
}

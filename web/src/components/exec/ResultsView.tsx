import { useMemo, useState } from "react";
import { ArrowLeft, Download, FileSpreadsheet, Loader2 } from "lucide-react";
import { ExecuteResult } from "@/lib/api/schemas";
import { ApiError } from "@/lib/api/client";
import { downloadXlsx } from "@/lib/api/endpoints";
import { classifyColumns } from "@/lib/derive/columns";
import { deriveKpis } from "@/lib/derive/kpis";
import { pickChart } from "@/lib/derive/chart";
import { downloadCsv, slugify } from "@/lib/export";
import { SummaryBand } from "./SummaryBand";
import { KpiCard } from "./KpiCard";
import { DriverChart } from "./DriverChart";
import { ResultGrid } from "./ResultGrid";
import { EmailDialog } from "./EmailDialog";

// The executive results hierarchy (B-6): summary → KPIs → driver chart → detail
// grid. Bands 1–3 are fixed; only the grid (band 4) scrolls (B-3). All KPI/chart
// derivation is local — no row data leaves the browser.
export function ResultsView({
  question,
  sql,
  result,
  onBack,
}: {
  question: string;
  sql: string;
  result: ExecuteResult;
  onBack?: () => void;
}) {
  const cols = useMemo(() => classifyColumns(result.columns, result.rows), [result]);
  const kpis = useMemo(() => deriveKpis(result.rows, cols), [result, cols]);
  const chart = useMemo(() => pickChart(result.rows, cols), [result, cols]);
  const filename = useMemo(() => slugify(question) || "result", [question]);

  const [xlsxBusy, setXlsxBusy] = useState(false);
  const [exportErr, setExportErr] = useState<string | null>(null);

  async function exportXlsx() {
    setExportErr(null);
    setXlsxBusy(true);
    try {
      await downloadXlsx({ columns: result.columns, rows: result.rows, filename });
    } catch (e) {
      setExportErr(e instanceof ApiError ? e.message : "Excel export failed.");
    } finally {
      setXlsxBusy(false);
    }
  }

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

      {chart && (
        <div className="shrink-0">
          <DriverChart spec={chart} />
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-card border border-hairline bg-surface">
        <div className="flex shrink-0 items-center justify-between border-b border-hairline px-3.5 py-2.5">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">
            Detail · {result.row_count.toLocaleString()} rows
          </span>
          <div className="flex items-center gap-2">
            {exportErr && <span className="text-[11.5px] text-loss">{exportErr}</span>}
            <button
              type="button"
              onClick={() => downloadCsv(filename, result.columns, result.rows)}
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
            <EmailDialog question={question} columns={result.columns} rows={result.rows} filename={filename} />
          </div>
        </div>
        <div className="min-h-0 flex-1">
          <ResultGrid result={result} cols={cols} />
        </div>
      </div>
    </div>
  );
}

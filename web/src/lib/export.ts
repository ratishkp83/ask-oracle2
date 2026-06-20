// Client-side CSV export of the shown result (no server round-trip). Excel is
// available via the email action (server-side xlsx) and a direct .xlsx download
// is a tracked follow-up.
export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48);
}

function csvCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildCsv(columns: string[], rows: unknown[][]): string {
  const head = columns.map(csvCell).join(",");
  const body = rows.map((r) => r.map(csvCell).join(",")).join("\n");
  return `${head}\n${body}`;
}

export function downloadCsv(name: string, columns: string[], rows: unknown[][]): void {
  const blob = new Blob([buildCsv(columns, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// Download a prebuilt HTML document (the cascading report bundle, ADR-026) as a
// single self-contained .html file — pure client, no server round-trip.
export function downloadHtml(name: string, html: string): void {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

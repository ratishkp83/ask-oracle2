import { formatCell, formatCompact, humanize } from "@/lib/format";
import { ChartSpec } from "../derive/chart";
import { BundleResult, BundleSection } from "./bundle";

// Render a cascade bundle to a SELF-CONTAINED, script-free HTML document (ADR-026):
// inline token-styled CSS, inline-SVG charts, every data value/identifier escaped
// (P10-R6). Opens offline; safe to email/archive. No external assets, no <script>.

export interface BundleMeta {
  title: string;
  question: string;
  generatedAt?: string; // ISO; defaults to now
  sql?: string; // shown in a collapsed "source query" disclosure
}

// --- escaping ---------------------------------------------------------------
const ESC: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
function esc(v: unknown): string {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
}
function trunc(s: string, n = 28): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// --- charts (inline SVG, no script) -----------------------------------------
function barSvg(spec: ChartSpec): string {
  const data = spec.data;
  const max = Math.max(1, ...data.map((d) => Math.abs(d.value)));
  const W = 560, labelW = 150, valW = 90, rowH = 26, pad = 8;
  const barArea = W - labelW - valW;
  const H = pad * 2 + data.length * rowH;
  const rows = data
    .map((d, i) => {
      const y = pad + i * rowH;
      const bw = Math.max(2, Math.round((Math.abs(d.value) / max) * barArea));
      return (
        `<text x="0" y="${y + 16}" class="lbl">${esc(trunc(d.label, 22))}</text>` +
        `<rect x="${labelW}" y="${y + 5}" width="${bw}" height="15" rx="3" class="bar"/>` +
        `<text x="${labelW + bw + 6}" y="${y + 16}" class="val">${esc(formatCompact(d.value, spec.currency))}</text>`
      );
    })
    .join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${esc(spec.measureName)} by ${esc(spec.dimensionName)}">${rows}</svg>`;
}

function lineSvg(spec: ChartSpec): string {
  const data = spec.data;
  const W = 560, H = 150, padL = 10, padR = 10, padT = 12, padB = 28;
  const vals = data.map((d) => d.value);
  const max = Math.max(...vals);
  const min = Math.min(...vals, 0);
  const span = max - min || 1;
  const x = (i: number) => padL + (data.length === 1 ? 0 : (i / (data.length - 1)) * (W - padL - padR));
  const y = (v: number) => padT + (1 - (v - min) / span) * (H - padT - padB);
  const pts = data.map((d, i) => `${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ");
  const dots = data.map((d, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(d.value).toFixed(1)}" r="2.5" class="dot"/>`).join("");
  const first = `<text x="${padL}" y="${H - 8}" class="lbl">${esc(trunc(data[0].label, 16))}</text>`;
  const last = `<text x="${W - padR}" y="${H - 8}" text-anchor="end" class="lbl">${esc(trunc(data[data.length - 1].label, 16))}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img" aria-label="${esc(spec.measureName)} over ${esc(spec.dimensionName)}"><polyline points="${pts}" class="line"/>${dots}${first}${last}</svg>`;
}

function chartHtml(spec: ChartSpec | null): string {
  if (!spec) return "";
  const more = spec.extra > 0 ? `<div class="more">+${spec.extra} more</div>` : "";
  const eyebrow = `<div class="eyebrow">${esc(humanize(spec.measureName))} by ${esc(humanize(spec.dimensionName))}</div>`;
  return `<div class="chart">${eyebrow}${spec.type === "line" ? lineSvg(spec) : barSvg(spec)}${more}</div>`;
}

// --- pieces -----------------------------------------------------------------
function kpisHtml(s: BundleSection): string {
  if (s.kpis.length === 0) return "";
  const cards = s.kpis
    .map(
      (k) =>
        `<div class="kpi"><div class="kpi-label">${esc(k.label)}</div><div class="kpi-value num">${esc(k.value)}</div><div class="kpi-ctx">${esc(k.context)}</div></div>`,
    )
    .join("");
  return `<div class="kpis">${cards}</div>`;
}

function insightsHtml(s: BundleSection): string {
  if (s.insights.length === 0) return "";
  const items = s.insights.map((i) => `<li>${esc(i.text)}</li>`).join("");
  return `<div class="insight"><div class="insight-h">What stands out</div><ul>${items}</ul></div>`;
}

function tableHtml(columns: string[], rows: unknown[][]): string {
  if (rows.length === 0) return "";
  const head = columns.map((c) => `<th>${esc(humanize(c))}</th>`).join("");
  const body = rows
    .map((r) => `<tr>${columns.map((_, i) => `<td>${esc(formatCell(r[i]))}</td>`).join("")}</tr>`)
    .join("");
  return `<table class="grid"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function othersHtml(s: BundleSection): string {
  return s.othersRollup ? `<div class="others">+ ${esc(s.othersRollup.label)} not expanded</div>` : "";
}

function sectionTitle(s: BundleSection): string {
  if (s.path.length === 0) return "";
  return s.path.map((p) => esc(p.value)).join(" › ");
}

function sectionHtml(s: BundleSection, columns: string[], depth: number): string {
  if (s.error) {
    return `<section class="sec err"><div class="sec-h">${sectionTitle(s)}</div><div class="err-msg">${esc(s.error)}</div></section>`;
  }
  const head = s.path.length > 0 ? `<div class="sec-h">${sectionTitle(s)} <span class="rc num">· ${s.rowCount.toLocaleString()} rows</span></div>` : "";
  const body =
    insightsHtml(s) +
    kpisHtml(s) +
    chartHtml(s.chart) +
    (s.detailRows ? tableHtml(columns, s.detailRows) : "") +
    othersHtml(s);
  const kids = s.children.map((c) => sectionHtml(c, columns, depth + 1)).join("");
  const cls = depth === 0 ? "sec root" : "sec";
  return `<section class="${cls}">${head}${body}${kids ? `<div class="kids">${kids}</div>` : ""}</section>`;
}

function tocHtml(root: BundleSection): string {
  if (root.children.length === 0) return "";
  const items = root.children
    .filter((c) => !c.error)
    .map((c) => `<li>${esc(c.path[c.path.length - 1]?.value ?? "")}</li>`)
    .join("");
  return items ? `<div class="toc"><div class="toc-h">Sections</div><ul>${items}</ul></div>` : "";
}

// --- document ---------------------------------------------------------------
const STYLE = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #F7F6F3; color: #16191F;
    font: 14px/1.5 -apple-system, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif; }
  .num { font-variant-numeric: tabular-nums; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 32px 24px 56px; }
  h1 { font-family: Georgia, "Times New Roman", serif; font-size: 26px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.01em; }
  .meta { color: #8A9099; font-size: 12.5px; margin-bottom: 20px; }
  .toc { background: #fff; border: 1px solid #E5E2DB; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; }
  .toc-h, .insight-h, .eyebrow, .kpi-label { text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; font-weight: 600; color: #5A6068; }
  .toc ul { margin: 6px 0 0; padding-left: 18px; columns: 2; }
  .sec { margin-top: 18px; }
  .sec.root { margin-top: 0; }
  .kids { margin-top: 12px; padding-left: 16px; border-left: 2px solid #E4EEEE; }
  .sec-h { font-family: Georgia, serif; font-size: 16px; font-weight: 600; color: #0E5C63; margin: 14px 0 8px; }
  .sec-h .rc { color: #8A9099; font-size: 12px; font-weight: 400; }
  .insight { background: #E4EEEE; border-left: 3px solid #0E5C63; border-radius: 8px; padding: 10px 12px; margin: 8px 0; }
  .insight-h { color: #0E5C63; }
  .insight ul { margin: 6px 0 0; padding-left: 18px; }
  .insight li { margin: 2px 0; }
  .kpis { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
  .kpi { flex: 1 1 150px; background: #fff; border: 1px solid #E5E2DB; border-radius: 12px; padding: 10px 12px; }
  .kpi-value { font-size: 20px; font-weight: 600; margin: 2px 0; }
  .kpi-ctx { color: #8A9099; font-size: 11.5px; }
  .chart { background: #fff; border: 1px solid #E5E2DB; border-radius: 12px; padding: 12px 14px; margin: 10px 0; }
  .chart .eyebrow { margin-bottom: 6px; }
  .bar { fill: #0E5C63; }
  .lbl { fill: #5A6068; font-size: 11px; }
  .val { fill: #16191F; font-size: 11px; font-variant-numeric: tabular-nums; }
  .line { fill: none; stroke: #0E5C63; stroke-width: 2; }
  .dot { fill: #0E5C63; }
  .more { color: #8A9099; font-size: 11.5px; margin-top: 4px; }
  .others { color: #8A9099; font-size: 12px; margin: 6px 0; }
  table.grid { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12.5px; }
  table.grid th { text-align: left; color: #5A6068; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #E5E2DB; padding: 5px 8px; }
  table.grid td { border-bottom: 1px solid #F1EFEA; padding: 5px 8px; font-variant-numeric: tabular-nums; }
  .err { color: #B42318; } .err-msg { color: #B42318; font-size: 12.5px; }
  details { margin-top: 24px; color: #5A6068; font-size: 12px; }
  details pre { white-space: pre-wrap; background: #fff; border: 1px solid #E5E2DB; border-radius: 8px; padding: 10px; }
  .trunc { color: #B25E09; font-size: 12px; margin-top: 10px; }
`;

export function renderBundleHtml(bundle: BundleResult, meta: BundleMeta): string {
  const when = meta.generatedAt ?? new Date().toISOString();
  const sqlBlock = meta.sql
    ? `<details><summary>Source query</summary><pre>${esc(meta.sql)}</pre></details>`
    : "";
  const truncNote = bundle.truncated
    ? `<div class="trunc">Some sections were limited to keep this report a sensible size.</div>`
    : "";
  const inner =
    `<h1>${esc(meta.title)}</h1>` +
    `<div class="meta">${esc(meta.question)} · generated ${esc(when)}</div>` +
    tocHtml(bundle.root) +
    sectionHtml(bundle.root, bundle.columns, 0) +
    truncNote +
    sqlBlock;
  return (
    `<!doctype html><html lang="en"><head><meta charset="utf-8"/>` +
    `<meta name="viewport" content="width=device-width, initial-scale=1"/>` +
    `<title>${esc(meta.title)}</title><style>${STYLE}</style></head>` +
    `<body><div class="wrap">${inner}</div></body></html>`
  );
}

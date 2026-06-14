import { isNumeric, toNumber } from "@/lib/format";

// Local column classification over the result set — used to derive KPIs, pick a
// chart, and align the grid. Pure heuristics on column-name *tokens* + sampled
// values; never sends data anywhere. Tokenizing (not substring) avoids false
// positives like "overdue" matching the currency word "due".
export type ColType = "number" | "currency" | "percent" | "date" | "id" | "category" | "text";

export interface ColumnMeta {
  name: string;
  index: number;
  type: ColType;
  isMeasure: boolean; // numeric & not an id → can be aggregated
  isInteger: boolean; // all sampled values whole → format aggregates as integers
  numericAligned: boolean; // right-align in the grid
}

const CURRENCY_WORDS = /^(amount|amt|total|subtotal|balance|outstanding|revenue|sales|cost|cogs|price|spend|due|paid|payment|value|charge|fee|net|gross)$/;
const PERCENT_WORDS = /^(pct|percent|rate|ratio|margin|share)$/;
const DATE_WORDS = /^(date|datetime|period|month|quarter|day|year|created|updated|posted|dt)$/;
const MEASURE_PRIORITY_WORDS = /^(outstanding|total|amount|revenue|sales|balance|due|spend|cost|net|gross)$/;
const ID_HINT = /(^id$|_id$|number$|_num$|^num$|code$|_no$)/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2})?/;

function tokens(name: string): string[] {
  return name.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function anyToken(toks: string[], re: RegExp): boolean {
  return toks.some((t) => re.test(t));
}

function sampleColumn(rows: unknown[][], index: number, limit = 60): unknown[] {
  const out: unknown[] = [];
  for (let i = 0; i < rows.length && out.length < limit; i++) {
    const v = rows[i]?.[index];
    if (v !== null && v !== undefined && v !== "") out.push(v);
  }
  return out;
}

export function classifyColumns(columns: string[], rows: unknown[][]): ColumnMeta[] {
  return columns.map((name, index) => {
    const sample = sampleColumn(rows, index);
    const lname = name.toLowerCase();
    const toks = tokens(name);
    const allNumeric = sample.length > 0 && sample.every(isNumeric);
    const looksDate =
      anyToken(toks, DATE_WORDS) ||
      (sample.length > 0 && sample.every((v) => typeof v === "string" && ISO_DATE.test(v)));

    let type: ColType;
    if (looksDate && !allNumeric) type = "date";
    else if (allNumeric && ID_HINT.test(lname)) type = "id";
    else if (allNumeric && anyToken(toks, PERCENT_WORDS)) type = "percent";
    else if (allNumeric && anyToken(toks, CURRENCY_WORDS)) type = "currency";
    else if (allNumeric) type = "number";
    else if (ID_HINT.test(lname)) type = "id";
    else type = "category";

    const isMeasure = type === "number" || type === "currency" || type === "percent";
    const isInteger = allNumeric && sample.every((v) => Number.isInteger(toNumber(v)));
    return { name, index, type, isMeasure, isInteger, numericAligned: isMeasure || type === "id" };
  });
}

// Shared ranking so KPIs and the driver chart agree on the "most important"
// measure: currency first, then a priority word (outstanding/total/amount…),
// then column order.
export function rankMeasures(cols: ColumnMeta[]): ColumnMeta[] {
  return cols
    .filter((c) => c.isMeasure)
    .sort((a, b) => {
      const ca = a.type === "currency" ? 0 : 1;
      const cb = b.type === "currency" ? 0 : 1;
      if (ca !== cb) return ca - cb;
      const pa = anyToken(tokens(a.name), MEASURE_PRIORITY_WORDS) ? 0 : 1;
      const pb = anyToken(tokens(b.name), MEASURE_PRIORITY_WORDS) ? 0 : 1;
      return pa - pb;
    });
}

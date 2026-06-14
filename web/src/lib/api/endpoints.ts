import { downloadPost, get, post } from "./client";
import {
  EmailResultSchema,
  ExecuteSchema,
  HealthSchema,
  Nl2SqlSchema,
} from "./schemas";

export async function getHealth() {
  return HealthSchema.parse(await get("/health"));
}

export async function nl2sql(body: { natural_language: string; ebs_modules?: string[] }) {
  return Nl2SqlSchema.parse(await post("/nl2sql", body));
}

// The single SELECT-only chokepoint. The UI proposes via nl2sql, the user
// approves, then this runs the SQL — it is the only way the client runs queries.
export async function execute(body: {
  sql: string;
  profile_id?: string;
  connection?: unknown;
  max_rows?: number;
}) {
  return ExecuteSchema.parse(await post("/execute", body));
}

// Download the shown result as a server-built Excel file (no re-query, no LLM).
export async function downloadXlsx(body: { columns: string[]; rows: unknown[][]; filename: string }) {
  return downloadPost("/reports/export", { ...body, format: "xlsx" }, `${body.filename}.xlsx`);
}

// Email the already-fetched result (no re-query, no LLM). The body is user-typed.
export async function emailReport(body: {
  to: string;
  subject: string;
  body: string;
  attachment_format: "csv" | "xlsx";
  columns: string[];
  rows: unknown[][];
  cc?: string;
  filename?: string;
}) {
  return EmailResultSchema.parse(await post("/reports/email", body));
}

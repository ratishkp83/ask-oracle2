import { del, downloadPost, get, post, put } from "./client";
import {
  ConnectionTestSchema,
  EbsPackListSchema,
  EbsPackSchema,
  EmailResultSchema,
  ExecuteSchema,
  HealthSchema,
  IntrospectResultSchema,
  Nl2SqlSchema,
  ProfileListSchema,
  ProfilePublicSchema,
  ReportListSchema,
  ReportSchema,
  SchemaRecordSchema,
  SchemaSummaryListSchema,
  TemplateListSchema,
  type ReportParam,
} from "./schemas";

export async function getHealth() {
  return HealthSchema.parse(await get("/health"));
}

// Saved connection profiles. Returns id/name/current_schema (never a password);
// the UI picks a connection by id and the server resolves the secret.
export async function getProfiles() {
  return ProfileListSchema.parse(await get("/profiles"));
}

// Create a saved connection. The password is carried here exactly once, to be
// encrypted at rest server-side; it is never persisted in the browser (invariant
// 4). `current_schema` is the optional default schema (ADR-018). Either
// service_name or sid is required (enforced server-side; the form guides it).
export type ProfileCreateBody = {
  name: string;
  host: string;
  port: number;
  service_name?: string | null;
  sid?: string | null;
  current_schema?: string | null;
  username: string;
  password: string;
  environment: "DEV" | "TEST" | "PROD";
};

export async function createProfile(body: ProfileCreateBody) {
  return ProfilePublicSchema.parse(await post("/profiles", body));
}

export async function deleteProfile(id: string) {
  await del(`/profiles/${encodeURIComponent(id)}`);
}

// Test a saved profile by id (server resolves the secret). No request body.
export async function testProfile(id: string) {
  return ConnectionTestSchema.parse(await post(`/profiles/${encodeURIComponent(id)}/test`));
}

// Test an unsaved connection before saving it — the password is sent once and
// not persisted anywhere (the profile isn't created).
export type InlineConnection = {
  host: string;
  port: number;
  service_name?: string | null;
  sid?: string | null;
  username: string;
  password: string;
};

export async function testConnection(conn: InlineConnection) {
  return ConnectionTestSchema.parse(await post("/test-connection", conn));
}

// Saved schema snapshots (data dictionaries). Names/metadata only — used as
// NL→SQL context by id; never carries row data (invariant 3).
export async function getSchemas() {
  return SchemaSummaryListSchema.parse(await get("/schemas"));
}

// Full detail for one saved schema (tables/columns/relationships). Metadata only.
export async function getSchema(id: string) {
  return SchemaRecordSchema.parse(await get(`/schemas/${encodeURIComponent(id)}`));
}

export async function deleteSchema(id: string) {
  await del(`/schemas/${encodeURIComponent(id)}`);
}

// Introspect a live schema via the SELECT-only chokepoint (metadata only) and,
// when save is set, persist it (removes the E11 admin handoff). Uses the chosen
// connection by id — no DB secret is sent from the client (invariant 4).
export type IntrospectBody = {
  profile_id?: string;
  owner: string;
  table_like?: string;
  save?: boolean;
  name?: string | null;
};

export async function introspectSchema(body: IntrospectBody) {
  return IntrospectResultSchema.parse(await post("/schemas/introspect", body));
}

// Curated EBS metadata packs (read-only). Names/descriptions/glossary only.
export async function getPacks() {
  return EbsPackListSchema.parse(await get("/packs"));
}

export async function getPack(module: string) {
  return EbsPackSchema.parse(await get(`/packs/${encodeURIComponent(module)}`));
}

export async function nl2sql(body: {
  natural_language: string;
  schema_id?: string;
  ebs_modules?: string[];
  // Per-session model override (ADR-004); omitted → server's configured model.
  llm?: { provider?: string; model?: string; api_key?: string; base_url?: string };
}) {
  return Nl2SqlSchema.parse(await post("/nl2sql", body));
}

// The single SELECT-only chokepoint. The UI proposes via nl2sql, the user
// approves, then this runs the SQL — it is the only way the client runs queries.
export async function execute(body: {
  sql: string;
  profile_id?: string;
  connection?: unknown;
  max_rows?: number;
  binds?: Record<string, unknown>; // Phase 4 server contract; used by Inc 4 Pull-detail.
}) {
  return ExecuteSchema.parse(await post("/execute", body));
}

// Saved reports (CRUD). A report is a saved SELECT/CTE + optional typed params.
export type ReportCreateBody = {
  name: string;
  description?: string;
  sql?: string;
  parameters?: ReportParam[];
  default_profile_id?: string | null;
  template_id?: string | null;
};

export async function getReports() {
  return ReportListSchema.parse(await get("/reports"));
}

export async function createReport(body: ReportCreateBody) {
  return ReportSchema.parse(await post("/reports", body));
}

export async function updateReport(id: string, body: ReportCreateBody) {
  return ReportSchema.parse(await put(`/reports/${encodeURIComponent(id)}`, body));
}

export async function deleteReport(id: string) {
  await del(`/reports/${encodeURIComponent(id)}`);
}

// Run a saved report through the same SELECT-only chokepoint as /execute, with
// typed binds coerced server-side from the report's parameters (ADR-007). The
// connection is by id (session override or the report's bound profile).
export async function runReport(
  id: string,
  body: { profile_id?: string; binds?: Record<string, unknown>; max_rows?: number },
) {
  return ExecuteSchema.parse(await post(`/reports/${encodeURIComponent(id)}/run`, body));
}

// Curated EBS report templates (read-only) — starting points for a new report.
export async function getTemplates() {
  return TemplateListSchema.parse(await get("/templates"));
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

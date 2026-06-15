import { del, downloadPost, get, post } from "./client";
import {
  ConnectionTestSchema,
  EmailResultSchema,
  ExecuteSchema,
  HealthSchema,
  Nl2SqlSchema,
  ProfileListSchema,
  ProfilePublicSchema,
  SchemaSummaryListSchema,
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

export async function nl2sql(body: {
  natural_language: string;
  schema_id?: string;
  ebs_modules?: string[];
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

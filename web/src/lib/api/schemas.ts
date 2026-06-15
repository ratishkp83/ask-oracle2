import { z } from "zod";

// Zod mirrors of the /v1 contracts — validated at the boundary so the UI never
// trusts an unexpected shape. Confirmed against src/api.py.

export const HealthSchema = z.object({ status: z.string() });
export type Health = z.infer<typeof HealthSchema>;

// Connection profiles — mirrors ProfilePublic (src/core/profiles.py). Never a
// password: the client only ever holds the profile id (invariant 4).
// `.catch` degrades gracefully on enum drift: an unexpected value defaults rather
// than throwing and failing the WHOLE list parse (ITM-027), so one odd record
// can't blank the picker.
export const EnvironmentSchema = z.enum(["DEV", "TEST", "PROD"]).catch("DEV");

export const ProfilePublicSchema = z.object({
  id: z.string(),
  name: z.string(),
  host: z.string(),
  port: z.number(),
  service_name: z.string().nullable().optional(),
  sid: z.string().nullable().optional(),
  current_schema: z.string().nullable().optional(),
  username: z.string(),
  environment: EnvironmentSchema,
});
export type ProfilePublic = z.infer<typeof ProfilePublicSchema>;

export const ProfileListSchema = z.array(ProfilePublicSchema);

// Result of a connection test (POST /profiles/{id}/test and POST /test-connection).
// The latter also returns a probe column/row; the UI only needs ok + timing, so
// any extra keys are ignored. A failed test surfaces as an ApiError, not ok:false.
export const ConnectionTestSchema = z.object({
  ok: z.boolean(),
  elapsed_seconds: z.number(),
});
export type ConnectionTest = z.infer<typeof ConnectionTestSchema>;

// Saved schema snapshots — mirrors SchemaSummary (src/core/schema_store.py).
// Names/metadata only; no row data ever (invariant 3).
export const SchemaSourceSchema = z.enum(["upload", "introspection"]).catch("upload");

export const SchemaSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  source: SchemaSourceSchema,
  profile_id: z.string().nullable().optional(),
  table_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type SchemaSummary = z.infer<typeof SchemaSummarySchema>;

export const SchemaSummaryListSchema = z.array(SchemaSummarySchema);

export const ConfidenceSchema = z
  .object({ level: z.string(), reasons: z.array(z.string()).default([]) })
  .nullable();
export type Confidence = z.infer<typeof ConfidenceSchema>;

export const Nl2SqlSchema = z.object({
  sql: z.string(),
  explanation: z.string().nullable().optional(),
  confidence: ConfidenceSchema.optional(),
});
export type Nl2SqlResult = z.infer<typeof Nl2SqlSchema>;

export const ExecuteSchema = z.object({
  columns: z.array(z.string()),
  rows: z.array(z.array(z.any())),
  elapsed_seconds: z.number(),
  row_count: z.number(),
  truncated: z.boolean(),
});
export type ExecuteResult = z.infer<typeof ExecuteSchema>;

export const EmailResultSchema = z.object({
  status: z.string(),
  message: z.string(),
  recipients: z.number().optional(),
  attachment_bytes: z.number().optional(),
});
export type EmailResult = z.infer<typeof EmailResultSchema>;

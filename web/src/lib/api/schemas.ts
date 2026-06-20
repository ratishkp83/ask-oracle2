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

export const EngineSchema = z.enum(["oracle", "postgres"]).catch("oracle");

export const ProfilePublicSchema = z.object({
  id: z.string(),
  name: z.string(),
  engine: EngineSchema.default("oracle"),
  host: z.string(),
  port: z.number(),
  service_name: z.string().nullable().optional(),
  sid: z.string().nullable().optional(),
  database: z.string().nullable().optional(),
  sslmode: z.string().nullable().optional(),
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

// Full schema detail (GET /schemas/{id}) — mirrors SchemaRecord + the serialized
// `definition` (schema_to_dict): tables keyed by name, each a list of columns,
// plus relationships. Metadata only — column names/types and PK/FK flags, never
// any row value (invariant 3).
export const SchemaColumnSchema = z.object({
  table_name: z.string().optional(),
  column_name: z.string(),
  data_type: z.string().nullable().optional(),
  is_primary_key: z.boolean().default(false),
  is_foreign_key: z.boolean().default(false),
  references_table: z.string().nullable().optional(),
  references_column: z.string().nullable().optional(),
});

export const SchemaRelationshipSchema = z.object({
  from_table: z.string(),
  from_column: z.string(),
  to_table: z.string(),
  to_column: z.string(),
  relationship_type: z.string().nullable().optional(),
});

export const SchemaDefinitionSchema = z.object({
  tables: z.record(z.array(SchemaColumnSchema)).default({}),
  relationships: z.array(SchemaRelationshipSchema).default([]),
});

export const SchemaRecordSchema = z.object({
  id: z.string(),
  name: z.string(),
  source: SchemaSourceSchema,
  profile_id: z.string().nullable().optional(),
  table_count: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  definition: SchemaDefinitionSchema.default({ tables: {}, relationships: [] }),
});
export type SchemaRecord = z.infer<typeof SchemaRecordSchema>;

// Result of POST /schemas/introspect. The large `definition` blob is ignored
// here (the saved schema is re-fetched via /schemas); we only need the summary.
export const IntrospectResultSchema = z.object({
  table_count: z.number(),
  warnings: z.array(z.string()).default([]),
  truncated: z.boolean().default(false),
  saved: SchemaSummarySchema.nullable().optional(),
});
export type IntrospectResult = z.infer<typeof IntrospectResultSchema>;

// Phase 11 — Optimization Advisory (GET /schemas/{id}/advisory). Advise-only
// structural suggestions for the engineer/DBA; the app never executes DDL.
export const SuggestionSchema = z.object({
  kind: z.string(),
  target: z.string(),
  ddl_candidate: z.string(),
  rationale: z.string(),
  tradeoff: z.string(),
  severity: z.string(),
});
export type Suggestion = z.infer<typeof SuggestionSchema>;
export const AdvisoryResponseSchema = z.object({ advisory: z.array(SuggestionSchema).default([]) });

// Phase 11 — setup readiness gate (GET /schemas/{id}/readiness, D-L). `usable`
// is the soft/hard-block verdict; `checklist` lists each auto/human signal.
export const ReadinessCheckSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.string(), // ok | missing | unavailable | acknowledged
  detail: z.string().nullable().optional(),
});
export const ReadinessSchema = z.object({
  state: z.string(), // ready | not_optimized | incomplete
  usable: z.boolean().default(true),
  enforcement: z.string().default("soft"),
  checklist: z.array(ReadinessCheckSchema).default([]),
});
export type Readiness = z.infer<typeof ReadinessSchema>;
export const ReadinessResponseSchema = z.object({ readiness: ReadinessSchema });

// Curated EBS metadata packs (GET /packs, /packs/{module}) — mirrors EbsPack
// (src/core/ebs_packs.py). Names/descriptions/joins + a business glossary; no
// row data. `module` kept as a plain string to tolerate any future module.
export const EbsTableNoteSchema = z.object({
  table: z.string(),
  description: z.string(),
  key_columns: z.array(z.string()).default([]),
  joins: z.array(z.string()).default([]),
});

export const EbsGlossaryTermSchema = z.object({
  term: z.string(),
  table: z.string(),
  column: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
});

export const EbsPackSchema = z.object({
  module: z.string(),
  name: z.string(),
  tables: z.array(EbsTableNoteSchema).default([]),
  glossary: z.array(EbsGlossaryTermSchema).default([]),
});
export type EbsPack = z.infer<typeof EbsPackSchema>;

export const EbsPackListSchema = z.array(EbsPackSchema);

// Saved reports — mirrors Report/ReportParam (src/core/reports.py). A report is a
// saved SELECT/CTE plus optional typed parameters bound as :name at run time
// (ADR-007); the SQL still only runs through the server chokepoint (invariant 1).
export const ParamTypeSchema = z.enum(["string", "number", "date", "list"]).catch("string");

export const ReportParamSchema = z.object({
  name: z.string(),
  label: z.string().default(""),
  type: ParamTypeSchema,
  required: z.boolean().default(true),
  default: z.any().optional(),
  // Optional value-picker SELECT (col 1 = value, optional col 2 = label); drives
  // a live dropdown in the run dialog via the chokepoint.
  lookup_sql: z.string().nullable().optional(),
});
export type ReportParam = z.infer<typeof ReportParamSchema>;

// Persisted cascade plan (Phase 10, ADR-026) — mirrors CascadeSpec (src/core/
// reports.py), snake_case on the wire. Metadata only (column names + ints); never
// executed. The frontend maps this to/from the internal camelCase CascadeSpec
// (web/src/lib/cascade/spec.ts) at the boundary.
export const CascadePersistedSchema = z.object({
  dimension_order: z.array(z.string()).default([]),
  depth: z.number().default(2),
  children_per_level: z.number().default(8),
  rows_per_child: z.number().nullable().optional(),
});
export type CascadePersisted = z.infer<typeof CascadePersistedSchema>;

export const ReportSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().default(""),
  sql: z.string().default(""),
  parameters: z.array(ReportParamSchema).default([]),
  default_profile_id: z.string().nullable().optional(),
  template_id: z.string().nullable().optional(),
  cascade: CascadePersistedSchema.nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Report = z.infer<typeof ReportSchema>;

export const ReportListSchema = z.array(ReportSchema);

// Curated EBS report templates (read-only starting points). Carry full SQL +
// parameters so a template flows straight into the report editor.
export const TemplateSchema = z.object({
  id: z.string(),
  module: z.string(),
  name: z.string(),
  description: z.string().default(""),
  sql: z.string().default(""),
  parameters: z.array(ReportParamSchema).default([]),
});
export type Template = z.infer<typeof TemplateSchema>;

export const TemplateListSchema = z.array(TemplateSchema);

export const ConfidenceSchema = z
  .object({ level: z.string(), reasons: z.array(z.string()).default([]) })
  .nullable();
export type Confidence = z.infer<typeof ConfidenceSchema>;

export const Nl2SqlSchema = z.object({
  sql: z.string(),
  explanation: z.string().nullable().optional(),
  // The request restated as the model understood it (typo-corrected/disambiguated),
  // shown as "Showing results for: …" so results correlate to intent (Phase 11).
  interpreted_question: z.string().nullable().optional(),
  confidence: ConfidenceSchema.optional(),
  // Off-topic guard: false when the question isn't answerable from the data; then
  // `message` is a friendly reason and the UI proposes/runs nothing. Defaults keep
  // older responses (without these fields) working as answerable.
  answerable: z.boolean().default(true),
  message: z.string().nullable().optional(),
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

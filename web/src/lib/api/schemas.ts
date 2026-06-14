import { z } from "zod";

// Zod mirrors of the /v1 contracts — validated at the boundary so the UI never
// trusts an unexpected shape. Confirmed against src/api.py.

export const HealthSchema = z.object({ status: z.string() });
export type Health = z.infer<typeof HealthSchema>;

// Connection profiles — mirrors ProfilePublic (src/core/profiles.py). Never a
// password: the client only ever holds the profile id (invariant 4).
export const EnvironmentSchema = z.enum(["DEV", "TEST", "PROD"]);

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

export const ConfidenceSchema = z
  .object({ level: z.string(), reasons: z.array(z.string()).default([]) })
  .nullable();

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

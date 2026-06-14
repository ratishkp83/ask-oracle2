import { z } from "zod";

// Zod mirrors of the /v1 contracts — validated at the boundary so the UI never
// trusts an unexpected shape. Confirmed against src/api.py.

export const HealthSchema = z.object({ status: z.string() });
export type Health = z.infer<typeof HealthSchema>;

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

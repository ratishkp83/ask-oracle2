import { ReactNode, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Mail, Send } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { emailReport } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";

type Status = { kind: "idle" | "sending" | "ok" | "error"; message?: string };

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

// The "send" follow-up action. The email is REAL — the button names the
// recipients so the user confirms before sending. No LLM on this path; the body
// is user-typed and the shown rows are attached as-is.
export function EmailDialog({
  question,
  columns,
  rows,
  filename,
}: {
  question: string;
  columns: string[];
  rows: unknown[][];
  filename: string;
}) {
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const [cc, setCc] = useState("");
  const [subject, setSubject] = useState(question || "Report");
  const [body, setBody] = useState("Please find the attached report.");
  const [format, setFormat] = useState<"csv" | "xlsx">("xlsx");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  const recipients = to.split(/[,;\s]+/).filter(Boolean);
  const canSend = recipients.length > 0 && status.kind !== "sending";

  async function send() {
    setStatus({ kind: "sending" });
    try {
      const res = await emailReport({ to, cc, subject, body, attachment_format: format, columns, rows, filename });
      setStatus({ kind: "ok", message: res.message });
    } catch (e) {
      setStatus({
        kind: "error",
        message: errorMessage(e, "Couldn’t send the email. Please try again, or contact IT support."),
      });
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setStatus({ kind: "idle" });
      }}
    >
      <DialogTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3 py-1.5 text-[12px] font-medium text-white">
          <Mail className="h-3.5 w-3.5" /> Email
        </button>
      </DialogTrigger>
      <DialogContent className="bg-surface sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Email this result</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            Sends the {rows.length.toLocaleString()} shown rows as a {format.toUpperCase()} attachment. The email is
            real — check the recipient.
          </DialogDescription>
        </DialogHeader>

        {status.kind === "ok" ? (
          <div className="flex items-start gap-2 rounded-control bg-[#E7F3EC] px-3 py-2.5 text-[13px] text-gain">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{status.message}</span>
          </div>
        ) : (
          <div className="space-y-3">
            <Field label="To">
              <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="name@company.com" className={inputCls} />
            </Field>
            <Field label="Cc (optional)">
              <input value={cc} onChange={(e) => setCc(e.target.value)} className={inputCls} />
            </Field>
            <Field label="Subject">
              <input value={subject} onChange={(e) => setSubject(e.target.value)} className={inputCls} />
            </Field>
            <Field label="Message">
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} className={`${inputCls} resize-none`} />
            </Field>
            <Field label="Attach as">
              <div className="flex gap-1.5">
                {(["xlsx", "csv"] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFormat(f)}
                    className={`rounded-control border px-3 py-1.5 text-[12px] font-medium ${
                      format === f ? "border-brand bg-brand-weak text-brand" : "border-hairline text-ink-muted"
                    }`}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </div>
            </Field>
            {status.kind === "error" && (
              <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{status.message}</span>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {status.kind === "ok" ? (
            <button onClick={() => setOpen(false)} className="rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white">
              Done
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!canSend}
              className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
            >
              {status.kind === "sending" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              {status.kind === "sending"
                ? "Sending…"
                : recipients.length
                  ? `Send to ${recipients.length} recipient${recipients.length > 1 ? "s" : ""}`
                  : "Send"}
            </button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">{label}</span>
      {children}
    </label>
  );
}

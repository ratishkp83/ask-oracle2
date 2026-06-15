import { ReactNode, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2, Plus, Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { createProfile, testConnection, type InlineConnection } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

type ConnectBy = "service" | "sid";
type Env = "DEV" | "TEST" | "PROD";
type TestStatus = { kind: "idle" | "testing" | "ok" | "error"; message?: string };

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

const EMPTY = {
  name: "",
  host: "",
  port: "1521",
  connectBy: "service" as ConnectBy,
  service_name: "",
  sid: "",
  username: "",
  password: "",
  current_schema: "",
  environment: "DEV" as Env,
};

// Add a saved connection (closes the E10 "add one in admin" handoff). The
// password is held only in local form state, sent once to create or test, and
// never persisted in the browser (invariant 4). "Test connection" probes the
// unsaved values via POST /test-connection so the user can verify before saving.
export function AddConnectionDialog() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(EMPTY);
  const [test, setTest] = useState<TestStatus>({ kind: "idle" });

  // Fields that change what a connection test actually probes — editing any of
  // them invalidates a prior pass/fail so a stale "Connected" can't mislead.
  const CONN_FIELDS: (keyof typeof EMPTY)[] = [
    "host",
    "port",
    "connectBy",
    "service_name",
    "sid",
    "username",
    "password",
  ];
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => {
    setF((prev) => ({ ...prev, [key]: value }));
    if (CONN_FIELDS.includes(key)) setTest((t) => (t.kind === "idle" ? t : { kind: "idle" }));
  };

  const portNum = Number(f.port);
  const portValid = Number.isInteger(portNum) && portNum >= 1 && portNum <= 65535;
  const connectField = f.connectBy === "service" ? f.service_name : f.sid;
  const complete =
    f.name.trim() &&
    f.host.trim() &&
    f.username.trim() &&
    f.password &&
    connectField.trim() &&
    portValid;

  // Shared inline-connection payload for both test and save (test omits name/env).
  function connectionPayload(): InlineConnection {
    return {
      host: f.host.trim(),
      port: portNum,
      service_name: f.connectBy === "service" ? f.service_name.trim() : null,
      sid: f.connectBy === "sid" ? f.sid.trim() : null,
      username: f.username.trim(),
      password: f.password,
    };
  }

  const save = useMutation({
    mutationFn: () =>
      createProfile({
        ...connectionPayload(),
        name: f.name.trim(),
        current_schema: f.current_schema.trim() || null,
        environment: f.environment,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profiles"] });
      reset();
      setOpen(false);
    },
  });

  function reset() {
    setF(EMPTY);
    setTest({ kind: "idle" });
    save.reset();
  }

  async function runTest() {
    if (!complete) return;
    setTest({ kind: "testing" });
    try {
      const res = await testConnection(connectionPayload());
      setTest({ kind: "ok", message: `Connected in ${res.elapsed_seconds.toFixed(2)}s` });
    } catch (e) {
      setTest({ kind: "error", message: errMsg(e) });
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90">
          <Plus className="h-4 w-4" /> Add connection
        </button>
      </DialogTrigger>
      <DialogContent className="bg-surface sm:max-w-[540px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Add a connection</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            The password is encrypted on the server and never stored in your browser. Read-only access is
            recommended.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Name" className="col-span-2">
            <input
              value={f.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Production GL"
              className={inputCls}
            />
          </Field>

          <Field label="Host">
            <input
              value={f.host}
              onChange={(e) => set("host", e.target.value)}
              placeholder="db.example.com"
              className={inputCls}
            />
          </Field>
          <Field label="Port">
            <input
              value={f.port}
              onChange={(e) => set("port", e.target.value)}
              inputMode="numeric"
              className={`${inputCls} ${f.port && !portValid ? "border-loss" : ""}`}
            />
          </Field>

          <Field label="Connect by" className="col-span-2">
            <div className="flex gap-1.5">
              {(
                [
                  ["service", "Service name"],
                  ["sid", "SID"],
                ] as const
              ).map(([val, lbl]) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => set("connectBy", val)}
                  className={`rounded-control border px-3 py-1.5 text-[12px] font-medium ${
                    f.connectBy === val ? "border-brand bg-brand-weak text-brand" : "border-hairline text-ink-muted"
                  }`}
                >
                  {lbl}
                </button>
              ))}
            </div>
          </Field>

          {f.connectBy === "service" ? (
            <Field label="Service name" className="col-span-2">
              <input
                value={f.service_name}
                onChange={(e) => set("service_name", e.target.value)}
                placeholder="ORCLPDB1"
                className={inputCls}
              />
            </Field>
          ) : (
            <Field label="SID" className="col-span-2">
              <input value={f.sid} onChange={(e) => set("sid", e.target.value)} placeholder="ORCL" className={inputCls} />
            </Field>
          )}

          <Field label="Username">
            <input
              value={f.username}
              onChange={(e) => set("username", e.target.value)}
              autoComplete="off"
              placeholder="aor_readonly"
              className={inputCls}
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={f.password}
              onChange={(e) => set("password", e.target.value)}
              autoComplete="new-password"
              className={inputCls}
            />
          </Field>

          <Field label="Default schema (optional)">
            <input
              value={f.current_schema}
              onChange={(e) => set("current_schema", e.target.value)}
              placeholder="AOR_DEMO"
              className={inputCls}
            />
          </Field>
          <Field label="Environment">
            <div className="flex gap-1.5">
              {(["DEV", "TEST", "PROD"] as const).map((env) => (
                <button
                  key={env}
                  type="button"
                  onClick={() => set("environment", env)}
                  className={`rounded-control border px-2.5 py-1.5 text-[12px] font-medium ${
                    f.environment === env ? "border-brand bg-brand-weak text-brand" : "border-hairline text-ink-muted"
                  }`}
                >
                  {env}
                </button>
              ))}
            </div>
          </Field>
        </div>

        {test.kind === "ok" && (
          <div className="flex items-start gap-2 rounded-control bg-[#E7F3EC] px-3 py-2 text-[12.5px] text-gain">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{test.message}</span>
          </div>
        )}
        {test.kind === "error" && (
          <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{test.message}</span>
          </div>
        )}
        {save.isError && (
          <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errMsg(save.error)}</span>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <button
            type="button"
            onClick={runTest}
            disabled={!complete || test.kind === "testing"}
            className="inline-flex items-center gap-1.5 rounded-control border border-hairline px-3.5 py-2 text-[13px] font-medium text-ink-muted transition-colors hover:border-brand hover:text-ink disabled:opacity-40"
          >
            {test.kind === "testing" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {test.kind === "testing" ? "Testing…" : "Test connection"}
          </button>
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={!complete || save.isPending}
            className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
          >
            {save.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            {save.isPending ? "Saving…" : "Save connection"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Friendly, sanitized message (+ ref id when present) — never raw driver text.
function errMsg(e: unknown): string {
  if (e instanceof ApiError) return e.errorId ? `${e.message} (ref ${e.errorId})` : e.message;
  return "Something went wrong. Please try again.";
}

function Field({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <label className={`block ${className ?? ""}`}>
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-faint">{label}</span>
      {children}
    </label>
  );
}

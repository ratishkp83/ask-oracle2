import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Database, Loader2, Plug, Trash2 } from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { deleteProfile, getProfiles, testProfile } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import type { ProfilePublic } from "@/lib/api/schemas";
import { AddConnectionDialog } from "./AddConnectionDialog";

// Connections admin screen (B6). Lists saved profiles and lets the user add, test,
// and delete them — so a connection can be set up without leaving for Streamlit
// (closes the E10 handoff). No DB secret ever lands here: profiles are referenced
// by id, the password is posted once at create-time (invariant 4). The frame never
// scrolls; the list region does (CXO single-viewport rule).
export function ConnectionsPage() {
  const { data: profiles, isLoading, isError, error } = useQuery({
    queryKey: ["profiles"],
    queryFn: getProfiles,
  });

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-hairline px-8 py-5">
        <div className="min-w-0">
          <h1 className="font-display text-[22px] font-semibold tracking-[-0.01em] text-ink">Connections</h1>
          <p className="mt-0.5 max-w-xl text-[13px] text-ink-muted">
            Saved Oracle connections. Add, test, or remove them — passwords are encrypted on the server and never
            stored in your browser.
          </p>
        </div>
        <AddConnectionDialog />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        {isLoading ? (
          <ListSkeleton />
        ) : isError ? (
          <ErrorState message={errorMessage(error)} />
        ) : !profiles || profiles.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="overflow-hidden rounded-card border border-hairline bg-surface shadow-e1">
            {profiles.map((p) => (
              <ConnectionRow key={p.id} profile={p} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

type TestStatus = { kind: "idle" | "testing" | "ok" | "error"; message?: string };

function ConnectionRow({ profile }: { profile: ProfilePublic }) {
  const [test, setTest] = useState<TestStatus>({ kind: "idle" });

  async function runTest() {
    setTest({ kind: "testing" });
    try {
      const res = await testProfile(profile.id);
      setTest({ kind: "ok", message: `Connected in ${res.elapsed_seconds.toFixed(2)}s` });
    } catch (e) {
      setTest({ kind: "error", message: errorMessage(e) });
    }
  }

  const connectBy = profile.service_name
    ? `Service · ${profile.service_name}`
    : profile.sid
      ? `SID · ${profile.sid}`
      : "—";

  return (
    <li className="flex items-center gap-4 border-b border-hairline px-4 py-3 last:border-b-0">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] bg-brand-weak text-brand">
        <Database className="h-4 w-4" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[14px] font-semibold text-ink">{profile.name}</span>
          <EnvBadge env={profile.environment} />
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px] text-ink-faint">
          <span className="truncate">
            {profile.username}@{profile.host}:{profile.port}
          </span>
          <span aria-hidden>·</span>
          <span className="truncate">{connectBy}</span>
          {profile.current_schema && (
            <>
              <span aria-hidden>·</span>
              <span className="truncate">Schema {profile.current_schema}</span>
            </>
          )}
        </div>
      </div>

      {/* Test result, inline next to the action. */}
      {test.kind === "ok" && (
        <span className="hidden items-center gap-1 text-[12px] font-medium text-gain sm:flex">
          <CheckCircle2 className="h-3.5 w-3.5" /> {test.message}
        </span>
      )}
      {test.kind === "error" && (
        <span className="hidden max-w-[260px] items-center gap-1 truncate text-[12px] font-medium text-loss sm:flex" title={test.message}>
          <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {test.message}
        </span>
      )}

      <button
        type="button"
        onClick={runTest}
        disabled={test.kind === "testing"}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-control border border-hairline px-3 py-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:border-brand hover:text-ink disabled:opacity-40"
      >
        {test.kind === "testing" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
        {test.kind === "testing" ? "Testing…" : "Test"}
      </button>

      <DeleteConnectionDialog profile={profile} />
    </li>
  );
}

function DeleteConnectionDialog({ profile }: { profile: ProfilePublic }) {
  const qc = useQueryClient();
  return (
    <ConfirmDialog
      triggerAriaLabel={`Delete ${profile.name}`}
      triggerClassName="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-control border border-hairline text-ink-faint transition-colors hover:border-loss hover:text-loss"
      triggerChildren={<Trash2 className="h-3.5 w-3.5" />}
      title="Delete connection"
      description={
        <>
          Remove <span className="font-medium text-ink">{profile.name}</span>? This deletes the saved credentials.
          Reports and schemas that reference it will need a new connection.
        </>
      }
      onConfirm={() => deleteProfile(profile.id)}
      onConfirmed={() => qc.invalidateQueries({ queryKey: ["profiles"] })}
    />
  );
}

function EnvBadge({ env }: { env: ProfilePublic["environment"] }) {
  const tone =
    env === "PROD"
      ? "bg-loss/10 text-loss"
      : env === "TEST"
        ? "bg-warn/10 text-warn"
        : "bg-surface-sunken text-ink-muted";
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] ${tone}`}>
      {env}
    </span>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-hairline bg-surface px-6 py-16 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-[11px] bg-brand-weak text-brand">
        <Plug className="h-5 w-5" />
      </div>
      <div>
        <p className="text-[15px] font-semibold text-ink">No connections yet</p>
        <p className="mt-1 max-w-sm text-[13px] text-ink-muted">
          Add your first Oracle connection to start asking questions. Read-only credentials are recommended.
        </p>
      </div>
      <AddConnectionDialog />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-card border border-loss/30 bg-loss/5 px-4 py-3 text-[13px] text-ink"
    >
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-loss" />
      <span>{message}</span>
    </div>
  );
}

function ListSkeleton() {
  return (
    <ul className="overflow-hidden rounded-card border border-hairline bg-surface">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex items-center gap-4 border-b border-hairline px-4 py-3.5 last:border-b-0">
          <div className="h-9 w-9 shrink-0 animate-pulse rounded-[9px] bg-surface-sunken" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-40 animate-pulse rounded bg-surface-sunken" />
            <div className="h-2.5 w-64 animate-pulse rounded bg-surface-sunken" />
          </div>
        </li>
      ))}
    </ul>
  );
}

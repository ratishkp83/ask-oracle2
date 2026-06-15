import { ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, CheckCircle2, Database, Loader2, ScanLine } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { getProfiles, introspectSchema } from "@/lib/api/endpoints";
import { errorMessage } from "@/lib/api/client";
import { useSession } from "@/app/session";

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

// Introspect a live schema and save it (closes the E11 admin handoff). Runs
// through the SELECT-only chokepoint server-side and reads metadata only — table
// and column names, never row data (invariant 3). The connection is referenced
// by the active session profile id; no DB secret is sent from the client (inv 4).
export function IntrospectDialog() {
  const qc = useQueryClient();
  const { profileId } = useSession();
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: getProfiles });
  const active = profiles?.find((p) => p.id === profileId) ?? null;

  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState("");
  const [tableLike, setTableLike] = useState("%");
  const [name, setName] = useState("");

  const run = useMutation({
    mutationFn: () =>
      introspectSchema({
        profile_id: profileId ?? undefined,
        owner: owner.trim(),
        table_like: tableLike.trim() || "%",
        save: true,
        name: name.trim() || null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schemas"] }),
  });

  function reset() {
    setOwner("");
    setTableLike("%");
    setName("");
    run.reset();
  }

  const canRun = !!profileId && !!owner.trim() && !run.isPending;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o && !owner && active?.current_schema) setOwner(active.current_schema);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-control bg-brand px-3.5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90">
          <ScanLine className="h-4 w-4" /> Read from database
        </button>
      </DialogTrigger>
      <DialogContent className="bg-surface sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">Read a schema from the database</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">
            Reads table and column metadata from the live database (read-only) and saves it as a dictionary. No row
            data is read or sent to the model.
          </DialogDescription>
        </DialogHeader>

        {/* Connection (by id — never a secret). Guide to Connections if none. */}
        {active ? (
          <div className="flex items-center gap-2 rounded-control bg-surface-sunken px-3 py-2 text-[12.5px] text-ink">
            <Database className="h-3.5 w-3.5 shrink-0 text-brand" />
            <span className="font-medium">{active.name}</span>
            <span className="text-ink-faint">
              · {active.username}@{active.host}
            </span>
          </div>
        ) : (
          <div className="flex items-start gap-2 rounded-control bg-[#FBF3E6] px-3 py-2 text-[12.5px] text-warn">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              No active connection.{" "}
              <Link to="/connections" className="font-medium text-brand hover:underline" onClick={() => setOpen(false)}>
                Add or select one
              </Link>{" "}
              first.
            </span>
          </div>
        )}

        {run.isSuccess ? (
          <div className="space-y-2">
            <div className="flex items-start gap-2 rounded-control bg-[#E7F3EC] px-3 py-2.5 text-[13px] text-gain">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Saved <span className="font-semibold">{run.data.saved?.name ?? owner.trim()}</span> ·{" "}
                {run.data.table_count} {run.data.table_count === 1 ? "table" : "tables"}
                {run.data.truncated ? " (truncated)" : ""}.
              </span>
            </div>
            {run.data.warnings.length > 0 && (
              <ul className="space-y-1 rounded-control bg-[#FBF3E6] px-3 py-2 text-[12px] text-warn">
                {run.data.warnings.slice(0, 5).map((w, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {w}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <Field label="Schema / owner">
              <input
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="e.g. AOR_DEMO"
                className={inputCls}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Table filter (optional)">
                <input value={tableLike} onChange={(e) => setTableLike(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Save as (optional)">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={owner.trim() ? `${owner.trim().toUpperCase()} (from database)` : "Dictionary name"}
                  className={inputCls}
                />
              </Field>
            </div>
            {run.isError && (
              <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{errorMessage(run.error)}</span>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {run.isSuccess ? (
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white"
            >
              Done
            </button>
          ) : (
            <button
              type="button"
              onClick={() => run.mutate()}
              disabled={!canRun}
              className="inline-flex items-center gap-1.5 rounded-control bg-brand px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
            >
              {run.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ScanLine className="h-3.5 w-3.5" />}
              {run.isPending ? "Reading…" : "Read & save"}
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

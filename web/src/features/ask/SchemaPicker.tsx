import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Check } from "lucide-react";
import { getSchemas } from "@/lib/api/endpoints";
import { ADMIN_URL } from "@/lib/config";
import { useSession } from "@/app/session";

// Inline schema selector that sits above the question box (decision 6: the schema
// lives in the Ask panel, not the TopBar). Writes the chosen schemaId into session
// context; defaults to the sole schema when exactly one exists. Names/metadata
// only — the schema is sent to the LLM by id, never row data (invariant 3).
// E11: when no schema is active, a calm non-blocking notice — nl2sql is still
// allowed, accuracy is just lower.
export function SchemaPicker() {
  const { schemaId, setSchemaId } = useSession();
  const { data: schemas, isLoading } = useQuery({
    queryKey: ["schemas"],
    queryFn: getSchemas,
  });

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Resolve the active selection once the list is known: keep a still-valid
  // remembered id; otherwise default to the sole schema, else force an explicit
  // choice (null → E11) so we never send a stale/unknown schema_id.
  useEffect(() => {
    if (!schemas) return;
    const stillValid = schemaId && schemas.some((s) => s.id === schemaId);
    if (stillValid) return;
    setSchemaId(schemas.length === 1 ? schemas[0].id : null);
  }, [schemas, schemaId, setSchemaId]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (isLoading) {
    return <div className="text-[12px] text-ink-faint">Schema · loading…</div>;
  }

  const active = schemas?.find((s) => s.id === schemaId) ?? null;
  const hasSchemas = !!schemas && schemas.length > 0;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
      {hasSchemas && (
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-ink-faint">Schema</span>
          <div ref={ref} className="relative">
            <button
              type="button"
              aria-haspopup="listbox"
              aria-expanded={open}
              aria-label="Active schema"
              onClick={() => setOpen((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-control border border-hairline bg-surface px-2.5 py-1 text-[12.5px] text-ink transition-colors hover:border-brand"
            >
              <span className="font-medium">{active ? active.name : "Select…"}</span>
              <ChevronDown className="h-3.5 w-3.5 text-ink-faint" />
            </button>

            {open && (
              <ul
                role="listbox"
                aria-label="Schemas"
                className="absolute left-0 z-20 mt-1.5 min-w-[220px] overflow-hidden rounded-card border border-hairline bg-surface py-1 shadow-e2"
              >
                {schemas!.map((s) => {
                  const selected = s.id === schemaId;
                  return (
                    <li key={s.id} role="option" aria-selected={selected}>
                      <button
                        type="button"
                        onClick={() => {
                          setSchemaId(s.id);
                          setOpen(false);
                        }}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-[12.5px] text-ink transition-colors hover:bg-surface-sunken"
                      >
                        <span className="flex min-w-0 flex-col">
                          <span className="truncate font-medium">{s.name}</span>
                          <span className="truncate text-[11px] text-ink-faint">
                            {s.table_count} {s.table_count === 1 ? "table" : "tables"} · {s.source}
                          </span>
                        </span>
                        {selected && <Check className="h-3.5 w-3.5 shrink-0 text-brand" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* E11 — non-blocking: no active schema (none chosen, or none exist yet). */}
      {!active && (
        <p role="note" className="text-[12px] text-ink-faint">
          No schema selected — accuracy may be lower.{" "}
          <a
            href={ADMIN_URL}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-brand hover:underline"
          >
            Add one in admin
          </a>
        </p>
      )}
    </div>
  );
}

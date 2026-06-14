import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Database, Plug } from "lucide-react";
import { getProfiles } from "@/lib/api/endpoints";
import { ADMIN_URL } from "@/lib/config";
import { useListboxNav } from "@/hooks/useListboxNav";
import { useSession } from "./session";

// The active-connection selector in the TopBar. Lists saved profiles and writes
// the chosen profileId into session context (never a secret — invariant 4). On
// load it defaults to the remembered id, falling back to the first profile.
// E10: zero profiles → a calm "add one in admin" affordance (Streamlit, beta).
export function ConnectionPicker() {
  const { profileId, setProfileId } = useSession();
  const { data: profiles, isLoading, isError } = useQuery({
    queryKey: ["profiles"],
    queryFn: getProfiles,
  });

  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const listNav = useListboxNav(open);

  // Default the selection once the list is known: keep a still-valid remembered
  // id, otherwise fall back to the first profile.
  useEffect(() => {
    if (!profiles) return;
    const stillValid = profileId && profiles.some((p) => p.id === profileId);
    if (!stillValid) setProfileId(profiles.length ? profiles[0].id : null);
  }, [profiles, profileId, setProfileId]);

  // Close on outside click / Escape.
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
    return (
      <span className="rounded-full border border-hairline bg-surface px-3 py-1.5 text-[12.5px] text-ink-faint">
        Loading connections…
      </span>
    );
  }

  // E10 — no connection configured (also covers an unreachable list). Render a
  // link to the admin surface when one is configured; otherwise just guidance
  // text (no broken link in a production bundle — ITM-028).
  if (isError || !profiles || profiles.length === 0) {
    const cls =
      "flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1.5 text-[12.5px] text-ink-muted";
    const body = (
      <>
        <Plug className="h-3.5 w-3.5 text-ink-faint" />
        No connection — add one in admin
      </>
    );
    return ADMIN_URL ? (
      <a
        href={ADMIN_URL}
        target="_blank"
        rel="noreferrer"
        className={`${cls} transition-colors hover:border-brand hover:text-ink`}
        title="Add a connection in admin"
      >
        {body}
      </a>
    ) : (
      <span className={cls}>{body}</span>
    );
  }

  const active = profiles.find((p) => p.id === profileId) ?? null;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Active connection"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1.5 text-[12.5px] text-ink transition-colors hover:border-brand"
      >
        <Database className="h-3.5 w-3.5 text-brand" />
        <span className="font-medium">{active ? active.name : "Select connection"}</span>
        {active?.current_schema && (
          <span className="text-ink-faint">· {active.current_schema}</span>
        )}
        <ChevronDown className="h-3.5 w-3.5 text-ink-faint" />
      </button>

      {open && (
        <ul
          ref={listNav.ref}
          onKeyDown={listNav.onKeyDown}
          role="listbox"
          aria-label="Connections"
          className="absolute right-0 z-20 mt-1.5 min-w-[240px] overflow-hidden rounded-card border border-hairline bg-surface py-1 shadow-e2"
        >
          {profiles.map((p) => {
            const selected = p.id === profileId;
            return (
              <li key={p.id} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => {
                    setProfileId(p.id);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-[12.5px] text-ink transition-colors hover:bg-surface-sunken"
                >
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-medium">{p.name}</span>
                    <span className="truncate text-[11px] text-ink-faint">
                      {p.current_schema ? `${p.current_schema} · ` : ""}
                      {p.username}@{p.host}
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
  );
}

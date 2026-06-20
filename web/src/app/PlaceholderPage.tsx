// Supporting screens (Reports, Data dictionary, Connections, Settings) land in
// B6; until then they show a calm, on-brand placeholder rather than a blank.
export function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <h1 className="font-display text-[22px] font-semibold text-ink">{title}</h1>
      <p className="max-w-md text-[14px] text-ink-muted">{subtitle}</p>
      <span className="mt-2 rounded-full bg-surface-sunken px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
        Coming in Phase 9
      </span>
    </div>
  );
}

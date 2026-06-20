import { useEffect, useRef, type KeyboardEvent } from "react";

// Roving arrow-key navigation for a hand-rolled listbox (ITM-029 / P9B-R1-F5).
// Attach the returned `ref` to the `<ul role="listbox">` and `onKeyDown` to it.
// On open, focus moves to the selected option (or the first); ArrowUp/Down wrap,
// Home/End jump. Option focus targets are the `<button>` inside each
// `[role="option"]`, which already handle Enter/Space to select.
export function useListboxNav(open: boolean) {
  const ref = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!open || !ref.current) return;
    const all = Array.from(ref.current.querySelectorAll<HTMLButtonElement>('[role="option"] button'));
    const selected = all.find(
      (b) => b.closest('[role="option"]')?.getAttribute("aria-selected") === "true",
    );
    (selected ?? all[0])?.focus();
  }, [open]);

  const onKeyDown = (e: KeyboardEvent) => {
    if (!ref.current) return;
    const all = Array.from(ref.current.querySelectorAll<HTMLButtonElement>('[role="option"] button'));
    if (all.length === 0) return;
    const i = all.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      all[i < 0 ? 0 : (i + 1) % all.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      all[i < 0 ? all.length - 1 : (i - 1 + all.length) % all.length]?.focus();
    } else if (e.key === "Home") {
      e.preventDefault();
      all[0]?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      all[all.length - 1]?.focus();
    }
  };

  return { ref, onKeyDown };
}

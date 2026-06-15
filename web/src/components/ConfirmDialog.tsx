import { ReactNode, useState } from "react";
import { AlertCircle, Loader2, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { errorMessage } from "@/lib/api/client";

// Shared destructive-confirm dialog (replaces the three near-identical delete
// dialogs across Connections / Data dictionary / Reports). The caller supplies the
// trigger appearance, the copy, and the async action; this owns the open state,
// the in-flight/await, and the sanitized error (invariant 5). `onConfirmed` runs
// after the action resolves (e.g. invalidate a query) and the dialog then closes.
export function ConfirmDialog({
  triggerAriaLabel,
  triggerClassName,
  triggerChildren,
  title,
  description,
  confirmLabel = "Delete",
  pendingLabel = "Deleting…",
  onConfirm,
  onConfirmed,
}: {
  triggerAriaLabel: string;
  triggerClassName: string;
  triggerChildren: ReactNode;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  pendingLabel?: string;
  onConfirm: () => Promise<unknown>;
  onConfirmed?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<{ kind: "idle" | "pending" | "error"; message?: string }>({
    kind: "idle",
  });

  async function confirm() {
    setState({ kind: "pending" });
    try {
      await onConfirm();
      onConfirmed?.();
      setOpen(false);
    } catch (e) {
      setState({ kind: "error", message: errorMessage(e) });
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setState({ kind: "idle" });
      }}
    >
      <button type="button" aria-label={triggerAriaLabel} onClick={() => setOpen(true)} className={triggerClassName}>
        {triggerChildren}
      </button>
      <DialogContent className="bg-surface sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="font-display text-[18px] font-semibold text-ink">{title}</DialogTitle>
          <DialogDescription className="text-[13px] text-ink-muted">{description}</DialogDescription>
        </DialogHeader>
        {state.kind === "error" && (
          <div className="flex items-start gap-2 rounded-control bg-[#FBECEC] px-3 py-2 text-[12.5px] text-loss">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{state.message}</span>
          </div>
        )}
        <DialogFooter className="gap-2 sm:gap-2">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-control border border-hairline px-4 py-2 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={state.kind === "pending"}
            className="inline-flex items-center gap-1.5 rounded-control bg-loss px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40"
          >
            {state.kind === "pending" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            {state.kind === "pending" ? pendingLabel : confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

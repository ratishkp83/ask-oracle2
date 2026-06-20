import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { getHealth } from "@/lib/api/endpoints";
import { ConnectionPicker } from "./ConnectionPicker";

export function TopBar() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });
  const online = !isError && data?.status === "ok";

  return (
    <header className="flex h-[52px] shrink-0 items-center justify-between border-b border-hairline bg-surface px-5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-[7px] bg-brand text-white">
          <Database className="h-3.5 w-3.5" />
        </div>
        <span className="font-display text-[17px] font-semibold tracking-[-0.01em] text-ink">
          Ask Oracle
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        <ConnectionPicker />
        <div
          className="flex items-center gap-2 rounded-full border border-hairline bg-surface px-3 py-1.5 text-[12.5px] text-ink"
          title={online ? "API connected" : isLoading ? "Connecting…" : "API offline"}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              online ? "bg-gain" : isLoading ? "bg-warn" : "bg-loss"
            }`}
          />
          {online ? "API connected" : isLoading ? "Connecting…" : "API offline"}
        </div>
      </div>
    </header>
  );
}

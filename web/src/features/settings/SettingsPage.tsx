import { ReactNode } from "react";
import { Cpu, Info, Lock, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { useSession, type LlmOverride } from "@/app/session";

const inputCls =
  "w-full rounded-control border border-hairline bg-surface px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-brand";

// Settings (B6, the lightest screen). Two parts: (1) a per-session model override
// (ADR-004) that's wired into the Ask flow's /nl2sql call — held in memory only,
// so the optional API key never touches browser storage; and (2) honest, read-only
// copy for the server-managed configuration (model, email, safety), which has no
// settings endpoint and is set by the administrator. The SELECT-only chokepoint
// always applies regardless of any override here (invariant 1).
export function SettingsPage() {
  const { llm, setLlm } = useSession();
  const patch = (p: Partial<LlmOverride>) => setLlm({ ...(llm ?? {}), ...p });
  const overriding = !!llm;

  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-hairline px-8 py-5">
        <h1 className="font-display text-[22px] font-semibold tracking-[-0.01em] text-ink">Settings</h1>
        <p className="mt-0.5 max-w-xl text-[13px] text-ink-muted">
          Set the AI model for your session. Connection and safety configuration is managed on the server.
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-2xl space-y-5">
          {/* Per-session model override */}
          <section className="rounded-card border border-hairline bg-surface p-5 shadow-e1">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-brand" />
              <h2 className="font-display text-[15px] font-semibold text-ink">AI model · this session</h2>
            </div>
            <p className="mt-1 text-[13px] text-ink-muted">
              Override the model used to turn your questions into SQL. Applies to your questions in this session only.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Field label="Provider">
                <select
                  aria-label="Provider"
                  value={llm?.provider ?? ""}
                  onChange={(e) => patch({ provider: e.target.value })}
                  className={inputCls}
                >
                  <option value="">Server default</option>
                  <option value="groq">Groq</option>
                  <option value="openai">OpenAI</option>
                </select>
              </Field>
              <Field label="Model">
                <input
                  value={llm?.model ?? ""}
                  onChange={(e) => patch({ model: e.target.value })}
                  placeholder="server default"
                  className={`${inputCls} num`}
                />
              </Field>
              <Field label="API key (optional)">
                <input
                  type="password"
                  value={llm?.api_key ?? ""}
                  onChange={(e) => patch({ api_key: e.target.value })}
                  autoComplete="off"
                  placeholder="use server key"
                  className={inputCls}
                />
              </Field>
              <Field label="Base URL (optional)">
                <input
                  value={llm?.base_url ?? ""}
                  onChange={(e) => patch({ base_url: e.target.value })}
                  placeholder="OpenAI-compatible endpoint"
                  className={`${inputCls} num`}
                />
              </Field>
            </div>

            <div className="mt-3 flex items-start gap-2 rounded-control bg-surface-sunken px-3 py-2 text-[12px] text-ink-muted">
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-faint" />
              <span>
                Used only for your requests this session. The API key is sent per request and is never stored in your
                browser.
              </span>
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-[12.5px] text-ink-muted" role="status">
                {overriding ? (
                  <>
                    <Sparkles className="-mt-0.5 mr-1 inline h-3.5 w-3.5 text-brand" />
                    Overriding this session
                    {llm?.model ? (
                      <>
                        : <span className="num font-medium text-ink">{llm.model}</span>
                      </>
                    ) : null}
                  </>
                ) : (
                  "Using the server’s configured model."
                )}
              </span>
              <button
                type="button"
                onClick={() => setLlm(null)}
                disabled={!overriding}
                className="rounded-control border border-hairline px-3 py-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:border-brand hover:text-ink disabled:opacity-40"
              >
                Reset to server default
              </button>
            </div>
          </section>

          {/* Server-managed configuration (informational) */}
          <section className="rounded-card border border-hairline bg-surface p-5">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-ink-faint" />
              <h2 className="font-display text-[15px] font-semibold text-ink">Managed on the server</h2>
            </div>
            <p className="mt-1 text-[13px] text-ink-muted">
              These are configured by your administrator and aren’t editable here.
            </p>
            <ul className="mt-3 divide-y divide-hairline">
              <ServerRow
                icon={<Cpu className="h-3.5 w-3.5" />}
                label="Default model"
                value="Set on the server (override above for your session)"
              />
              <ServerRow
                icon={<Mail className="h-3.5 w-3.5" />}
                label="Email delivery"
                value="Enabled when SMTP is configured on the server"
              />
              <ServerRow
                icon={<ShieldCheck className="h-3.5 w-3.5" />}
                label="Safety limits"
                value="SELECT-only chokepoint + row caps, always enforced"
              />
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}

function ServerRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <li className="flex items-center justify-between gap-4 py-2.5">
      <span className="flex items-center gap-2 text-[13px] font-medium text-ink">
        <span className="text-ink-faint">{icon}</span>
        {label}
      </span>
      <span className="text-right text-[12.5px] text-ink-muted">{value}</span>
    </li>
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

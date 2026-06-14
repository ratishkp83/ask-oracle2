import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// App-wide selection of the active connection (profileId) and schema (schemaId).
// DB secrets NEVER live here — connections are referenced by id and resolved
// server-side (invariant 4: the React app holds no DB passwords). The selection
// is persisted to localStorage so a reload keeps the chosen connection/schema.

type SessionState = {
  profileId: string | null;
  schemaId: string | null;
  setProfileId: (id: string | null) => void;
  setSchemaId: (id: string | null) => void;
};

const SessionContext = createContext<SessionState | null>(null);

const PROFILE_KEY = "aor.profileId";
const SCHEMA_KEY = "aor.schemaId";

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // localStorage unavailable (private mode / SSR) — start unselected.
    return null;
  }
}

function writeStored(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Persisting is best-effort; the selection still lives in memory.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<string | null>(() => readStored(PROFILE_KEY));
  const [schemaId, setSchemaIdState] = useState<string | null>(() => readStored(SCHEMA_KEY));

  const setProfileId = useCallback((id: string | null) => {
    setProfileIdState(id);
    writeStored(PROFILE_KEY, id);
  }, []);

  const setSchemaId = useCallback((id: string | null) => {
    setSchemaIdState(id);
    writeStored(SCHEMA_KEY, id);
  }, []);

  const value = useMemo<SessionState>(
    () => ({ profileId, schemaId, setProfileId, setSchemaId }),
    [profileId, schemaId, setProfileId, setSchemaId],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within a SessionProvider");
  return ctx;
}

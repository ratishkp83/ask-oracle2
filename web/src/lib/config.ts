// Runtime config. The API key (only needed when the deployment sets APP_API_KEY)
// is supplied via Vite env at build/run time — never hard-coded, never a DB
// secret. DB passwords never touch the client; connections are chosen by id.
export const API_BASE = (import.meta.env.VITE_AOR_API_BASE as string) || "/v1";
export const API_KEY = (import.meta.env.VITE_AOR_API_KEY as string) || "";

// Admin surface (the Streamlit app) where connections/schemas are added during
// beta. Overridable per deployment; defaults to the local Streamlit port.
export const ADMIN_URL =
  (import.meta.env.VITE_AOR_ADMIN_URL as string) || "http://localhost:8501";

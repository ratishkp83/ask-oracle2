// Runtime config. The API key (only needed when the deployment sets APP_API_KEY)
// is supplied via Vite env at build/run time — never hard-coded, never a DB
// secret. DB passwords never touch the client; connections are chosen by id.
export const API_BASE = (import.meta.env.VITE_AOR_API_BASE as string) || "/v1";
export const API_KEY = (import.meta.env.VITE_AOR_API_KEY as string) || "";

// Admin surface (the Streamlit app) where connections/schemas are added during
// beta. Set per deployment via VITE_AOR_ADMIN_URL. To avoid baking a wrong
// localhost URL into a production bundle (ITM-028), it only falls back to the
// local Streamlit port in a dev build; in production it stays empty and the UI
// shows guidance text without a (broken) link.
export const ADMIN_URL =
  (import.meta.env.VITE_AOR_ADMIN_URL as string) ||
  (import.meta.env.DEV ? "http://localhost:8501" : "");

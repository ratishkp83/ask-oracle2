import { API_BASE, API_KEY } from "@/lib/config";

// Uniform API error: surfaces the friendly message + the server's error_id /
// X-Request-ID so the UI can show a support reference, never raw driver text.
export class ApiError extends Error {
  status: number;
  errorId?: string;
  constructor(message: string, status: number, errorId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorId = errorId;
  }
}

// The single place the UI turns a thrown error into user-facing copy (invariant 5).
// The server already makes every `detail` it returns user-safe (it sanitizes raw
// driver/infra errors and only exposes intentional, readable messages), so those
// pass through verbatim with the support reference id. We only substitute a generic
// "contact IT support" message for the two cases with no usable server message: a
// network failure (the API is unreachable) and a bodyless HTTP failure where the
// client synthesised a "Request failed (NNN)" placeholder. Raw driver text never
// reaches here.
const DEFAULT_FALLBACK = "Something went wrong. Please try again — if it continues, contact IT support.";
const SUPPORT_GENERIC = "Something went wrong. Please try again, or contact IT support with this reference.";
// Client-synthesised placeholders from apiFetch/downloadPost (no server detail).
const OPAQUE_FALLBACK = /(?:Request|Export) failed \(\d{3}\)\.?$/i;

export function friendlyError(e: unknown, fallback = DEFAULT_FALLBACK): { message: string; errorId?: string } {
  if (e instanceof ApiError) {
    if (e.status === 0) {
      return { message: "Can’t reach the service. Check your connection, or contact IT support if this continues." };
    }
    if (!e.message || OPAQUE_FALLBACK.test(e.message)) {
      return { message: SUPPORT_GENERIC, errorId: e.errorId };
    }
    // A safe, user-facing server message (the server sanitises anything sensitive).
    return { message: e.message, errorId: e.errorId };
  }
  return { message: fallback };
}

// Convenience: a single-line message with the support reference appended.
export function errorMessage(e: unknown, fallback = DEFAULT_FALLBACK): string {
  const { message, errorId } = friendlyError(e, fallback);
  return errorId ? `${message} (ref ${errorId})` : message;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (API_KEY) headers.set("X-API-Key", API_KEY);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Network error — the API is unreachable.", 0);
  }

  const requestId = res.headers.get("X-Request-ID") || undefined;
  const text = await res.text();
  const data = text ? safeJson(text) : undefined;

  if (!res.ok) {
    const detail = pickDetail(data) || `Request failed (${res.status}).`;
    const errorId = (data && (data.error_id as string)) || requestId;
    throw new ApiError(detail, res.status, errorId);
  }
  return data as T;
}

function safeJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

// FastAPI uses `detail` (string) for HTTPExceptions and a list for 422s.
function pickDetail(data: any): string | undefined {
  if (!data) return undefined;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d: any) => d?.msg).filter(Boolean).join("; ") || undefined;
  }
  return undefined;
}

export function get<T>(path: string) {
  return apiFetch<T>(path);
}
// `body` is optional: some POSTs (e.g. POST /profiles/{id}/test) take no payload,
// in which case we send no body so no Content-Type header is set.
export function post<T>(path: string, body?: unknown) {
  return apiFetch<T>(path, body === undefined ? { method: "POST" } : { method: "POST", body: JSON.stringify(body) });
}
export function put<T>(path: string, body: unknown) {
  return apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) });
}
export function del<T = void>(path: string) {
  return apiFetch<T>(path, { method: "DELETE" });
}

// POST that returns a file and triggers a browser download. Used for server-side
// Excel/CSV export (the server builds the file so no spreadsheet lib ships here).
export async function downloadPost(path: string, body: unknown, fallbackName: string): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json", Accept: "*/*" });
  if (API_KEY) headers.set("X-API-Key", API_KEY);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  } catch {
    throw new ApiError("Network error — the API is unreachable.", 0);
  }
  if (!res.ok) {
    const data = await res.json().catch(() => undefined as any);
    const detail = (data && typeof data.detail === "string" && data.detail) || `Export failed (${res.status}).`;
    throw new ApiError(detail, res.status, data?.error_id || res.headers.get("X-Request-ID") || undefined);
  }

  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = m ? m[1] : fallbackName;
  a.click();
  URL.revokeObjectURL(url);
}

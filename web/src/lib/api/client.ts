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
export function post<T>(path: string, body: unknown) {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
}

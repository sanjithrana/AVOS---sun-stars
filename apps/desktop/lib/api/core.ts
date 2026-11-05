export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    public data?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_PORT = process.env.NEXT_PUBLIC_API_PORT || "8001";
const REQUEST_TIMEOUT_MS = 20_000;

/**
 * Base URL of the AVOS API, e.g. http://localhost:8001/api/v1.
 *
 * NEXT_PUBLIC_API_URL wins when set. Otherwise the API is assumed to run
 * on the same host that served this page, on port 8001 (docker-compose's
 * mapping). That's what makes opening the UI from another device -
 * http://192.168.1.12:3000 - work: a hardcoded "localhost" would point
 * that device's browser at *itself*.
 */
export function apiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${API_PORT}/api/v1`;
  }
  return `http://localhost:${API_PORT}/api/v1`;
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; project_id?: string };
  detail?: unknown;
  message?: string;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${endpoint}`, {
      ...options,
      signal: options.signal ?? controller.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    clearTimeout(timer);
    const aborted = error instanceof DOMException && error.name === "AbortError";
    throw new ApiError(
      0,
      aborted
        ? `The API at ${apiBaseUrl()} did not respond in time.`
        : `Cannot reach the API at ${apiBaseUrl()}. Is the backend running?`
    );
  }
  clearTimeout(timer);

  if (!response.ok) {
    let body: ErrorEnvelope | string | undefined;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    // Backend envelope is {"error": {"code", "message"}} (AVOS-10 s5).
    const envelope = typeof body === "object" ? body : undefined;
    const message =
      envelope?.error?.message ||
      envelope?.message ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message, envelope?.error?.code, body);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, string>) => {
    const query = params ? `?${new URLSearchParams(params).toString()}` : "";
    return request<T>(`${endpoint}${query}`, { method: "GET" });
  },
  post: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: "PUT",
      body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
    }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: "DELETE" }),
};

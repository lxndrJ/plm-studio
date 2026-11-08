// Typisierter API-Client. In M7 aus /openapi.json generiert (openapi-typescript);
// bis dahin schlanker handgeschriebener Wrapper für Phase 1.

const BASE = "/api/v1";

let token: string | null = null;

export function setToken(t: string | null) {
  token = t;
}

async function req<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`API ${status}`);
  }
}

export const health = () => fetch("/health").then((r) => r.json());
export const login = (email: string, password: string) =>
  req<{ access_token: string; role: string; email: string }>("POST", "/auth/login", { email, password });
export const listParts = (query?: string) => req<unknown[]>("GET", "/parts", undefined, query ? { query } : undefined);
export const createPart = (payload: unknown, direct = true) =>
  req("POST", "/parts", payload, { direct: String(direct) });
export const approveConfirmation = (id: string) => req("POST", `/confirmations/${id}/approve`);

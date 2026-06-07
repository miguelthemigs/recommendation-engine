export const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Set by AuthContext whenever the session changes */
let _accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(
      typeof detail === 'string'
        ? detail
        : (detail as { message?: string })?.message ?? `HTTP ${status}`,
    );
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };

  if (_accessToken) {
    headers['Authorization'] = `Bearer ${_accessToken}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail: unknown;
    const ct = res.headers.get('content-type') ?? '';
    if (ct.includes('application/json')) {
      try {
        const body = await res.json();
        detail = body?.detail ?? body;
      } catch {
        detail = res.statusText;
      }
    } else {
      detail = await res.text().catch(() => res.statusText);
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

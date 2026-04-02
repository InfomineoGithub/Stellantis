/**
 * Shared authenticated fetch helper for gateway API calls.
 *
 * Wraps the native `fetch` and injects the better-auth JWT token as an
 * `Authorization: Bearer <token>` header so every gateway endpoint can
 * enforce `Depends(get_current_user)` on the Python side.
 *
 * HOW IT WORKS:
 * - better-auth's `jwt()` plugin exposes a `GET /api/auth/token` endpoint.
 * - When a valid session cookie exists, that endpoint returns `{ token: "..." }`.
 * - We cache the token for 14 min (tokens expire in 15 min by default).
 */

// --- Token cache ---
let _cachedToken: string | null = null;
let _tokenExpiresAt = 0;
const TOKEN_TTL_MS = 14 * 60 * 1000; // 14 minutes

/**
 * Fetch a fresh JWT from the better-auth /api/auth/token endpoint.
 * Returns null if the user has no active session.
 */
async function fetchJwtToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/token", {
      method: "GET",
      credentials: "include", // send session cookie
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { token?: string };
    return data?.token ?? null;
  } catch {
    return null;
  }
}

/**
 * Return a cached JWT, refreshing if expired/missing.
 * Returns null when the user is not logged in.
 */
export async function getJwtToken(): Promise<string | null> {
  if (_cachedToken && Date.now() < _tokenExpiresAt) {
    return _cachedToken;
  }
  const token = await fetchJwtToken();
  if (token) {
    _cachedToken = token;
    _tokenExpiresAt = Date.now() + TOKEN_TTL_MS;
  } else {
    _cachedToken = null;
    _tokenExpiresAt = 0;
  }
  return token;
}

/** Clear the token cache (call on sign-out). */
export function clearJwtTokenCache(): void {
  _cachedToken = null;
  _tokenExpiresAt = 0;
}

/**
 * Return an Authorization header object, or {} if not authenticated.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const token = await getJwtToken();
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {
    // fall through
  }
  return {};
}

/**
 * Authenticated `fetch` wrapper.
 *
 * Usage:
 *   import { fetchWithAuth } from "@/core/api/auth-fetch";
 *   const res = await fetchWithAuth(`${getBackendBaseURL()}/api/models`);
 */
export async function fetchWithAuth(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  const authHeaders = await getAuthHeaders();
  return fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      ...authHeaders,
      ...init?.headers,
    },
  });
}

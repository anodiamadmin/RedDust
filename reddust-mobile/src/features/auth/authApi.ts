// src/features/auth/authApi.ts
// RedDust Step 19D.7.1 — adapter for the Step 19C Auth API.
import { AUTH_BASE } from "../../config/endpoints";

export type Platform = "android" | "ios";
export type RedDustUser = { id: string; display_name: string | null };
export type RefreshResponse = {
  auth_session_id: string;
  token_type: "Bearer";
  access_token: string;
  expires_in: number;
  refresh_token: string;
  refresh_expires_in: number;
};
export type SessionResponse = RefreshResponse & { user: RedDustUser };
export type UserPreferences = {
  preferred_persona: string | null;
  speaker_default: string | null;
};
export type MeResponse = {
  user: RedDustUser;
  preferences: UserPreferences | null;
};
export type HealthResponse = { status: "ok"; service: "reddust-auth-api" };

export class AuthApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status?: number,
  ) {
    super(
      `RedDust Auth API: ${code}${status === undefined ? "" : ` (HTTP ${status})`}`,
    );
    this.name = "AuthApiError";
  }
}

const TIMEOUT_MS = 15000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function invalid(): never {
  throw new AuthApiError("INVALID_RESPONSE");
}
function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return invalid();
  return value as Record<string, unknown>;
}
function exact(value: unknown, keys: string[]): Record<string, unknown> {
  const obj = record(value);
  if (
    Object.keys(obj).length !== keys.length ||
    keys.some((k) => !Object.prototype.hasOwnProperty.call(obj, k))
  )
    return invalid();
  return obj;
}
function uuid(value: unknown): string {
  if (typeof value !== "string" || !UUID.test(value)) return invalid();
  return value;
}
function nullableString(value: unknown): string | null {
  if (value !== null && typeof value !== "string") return invalid();
  return value;
}
function isCredential(value: unknown, max: number): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= max &&
    !/\s/.test(value)
  );
}
function credential(value: unknown, max: number): string {
  if (!isCredential(value, max)) return invalid();
  return value;
}
function seconds(value: unknown): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value <= 0 ||
    value > Math.floor(Number.MAX_SAFE_INTEGER / 1000)
  )
    return invalid();
  return value;
}
function parseUser(value: unknown): RedDustUser {
  const v = exact(value, ["id", "display_name"]);
  return { id: uuid(v.id), display_name: nullableString(v.display_name) };
}
const tokenKeys = [
  "auth_session_id",
  "token_type",
  "access_token",
  "expires_in",
  "refresh_token",
  "refresh_expires_in",
];
function parseTokens(v: Record<string, unknown>): RefreshResponse {
  if (v.token_type !== "Bearer") return invalid();
  return {
    auth_session_id: uuid(v.auth_session_id),
    token_type: "Bearer",
    access_token: credential(v.access_token, 16384),
    expires_in: seconds(v.expires_in),
    refresh_token: credential(v.refresh_token, 512),
    refresh_expires_in: seconds(v.refresh_expires_in),
  };
}
function parseLogin(value: unknown): SessionResponse {
  const v = exact(value, [...tokenKeys, "user"]);
  return { ...parseTokens(v), user: parseUser(v.user) };
}
function parseRefresh(value: unknown): RefreshResponse {
  return parseTokens(exact(value, tokenKeys));
}
function parseMe(value: unknown): MeResponse {
  const v = exact(value, ["user", "preferences"]);
  const p =
    v.preferences === null
      ? null
      : exact(v.preferences, ["preferred_persona", "speaker_default"]);
  return {
    user: parseUser(v.user),
    preferences:
      p === null
        ? null
        : {
            preferred_persona: nullableString(p.preferred_persona),
            speaker_default: nullableString(p.speaker_default),
          },
  };
}
function parseHealth(value: unknown): HealthResponse {
  const v = exact(value, ["status", "service"]);
  if (v.status !== "ok" || v.service !== "reddust-auth-api") return invalid();
  return { status: "ok", service: "reddust-auth-api" };
}

// Never include raw response bodies, credentials, or underlying fetch errors in errors/logs.
const safeCodes = new Set([
  "INVALID_GOOGLE_TOKEN",
  "ACCOUNT_OR_DEVICE_NOT_ALLOWED",
  "ACCOUNT_NOT_ALLOWED",
  "AUTH_UNAVAILABLE",
  "INVALID_REFRESH_TOKEN",
  "INVALID_ACCESS_TOKEN",
  "RATE_LIMITED",
]);
async function httpError(res: Response): Promise<AuthApiError> {
  let code = res.status === 422 ? "VALIDATION_ERROR" : `HTTP_${res.status}`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = body.detail;
      if (
        detail &&
        typeof detail === "object" &&
        "code" in detail &&
        typeof detail.code === "string" &&
        safeCodes.has(detail.code)
      )
        code = detail.code;
    }
  } catch {
    /* Keep safe status-based fallback. */
  }
  return new AuthApiError(code, res.status);
}
async function request<T>(
  method: "GET" | "POST",
  path: string,
  expected: 200 | 204,
  parse: (value: unknown) => T,
  body?: unknown,
  bearer?: string,
): Promise<T> {
  if (bearer !== undefined && !isCredential(bearer, 16384))
    throw new AuthApiError("INVALID_LOCAL_ACCESS_TOKEN");
  const target = `${AUTH_BASE}${path}`;
  if (!target.startsWith("https://")) throw new AuthApiError("HTTPS_REQUIRED");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(target, {
      method,
      signal: controller.signal,
      redirect: "error",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(bearer !== undefined ? { Authorization: `Bearer ${bearer}` } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    // Defense in depth: native React Native fetch may not honor redirect:'error'.
    // A post-response check cannot prevent credential forwarding by a native redirect.
    if (
      res.redirected ||
      (res.url && res.url !== target) ||
      (res.status >= 300 && res.status < 400)
    )
      throw new AuthApiError("UNEXPECTED_REDIRECT");
    if (!res.ok) throw await httpError(res);
    if (res.status !== expected)
      throw new AuthApiError("UNEXPECTED_STATUS", res.status);
    if (expected === 204) return parse(undefined);
    let json: unknown;
    try {
      json = await res.json();
    } catch {
      throw new AuthApiError("INVALID_RESPONSE");
    }
    return parse(json);
  } catch (error) {
    if (controller.signal.aborted) throw new AuthApiError("TIMEOUT");
    if (error instanceof AuthApiError) throw error;
    throw new AuthApiError("NETWORK_FAILURE");
  } finally {
    clearTimeout(timer);
  }
}

export async function exchangeGoogleIdToken(
  idToken: string,
  installationId: string,
  platform: Platform,
): Promise<SessionResponse> {
  if (
    !isCredential(idToken, 16384) ||
    !UUID.test(installationId) ||
    (platform !== "android" && platform !== "ios")
  )
    throw new AuthApiError("INVALID_LOCAL_LOGIN_REQUEST");
  return request("POST", "/v1/auth/google", 200, parseLogin, {
    id_token: idToken,
    installation_id: installationId,
    platform,
  });
}

// The caller MUST serialize refreshes and replace the stored refresh credential.
// Never automatically retry a refresh after an ambiguous timeout/network failure.
export async function refreshSession(
  refreshToken: string,
): Promise<RefreshResponse> {
  if (!isCredential(refreshToken, 512))
    throw new AuthApiError("INVALID_LOCAL_REFRESH_TOKEN");
  return request("POST", "/v1/auth/refresh", 200, parseRefresh, {
    refresh_token: refreshToken,
  });
}

export async function logoutSession(accessToken: string): Promise<void> {
  if (!isCredential(accessToken, 16384))
    throw new AuthApiError("INVALID_LOCAL_ACCESS_TOKEN");
  return request(
    "POST",
    "/v1/auth/logout",
    204,
    () => undefined,
    {},
    accessToken,
  );
}

export async function getCurrentUser(accessToken: string): Promise<MeResponse> {
  if (!isCredential(accessToken, 16384))
    throw new AuthApiError("INVALID_LOCAL_ACCESS_TOKEN");
  return request("GET", "/v1/users/me", 200, parseMe, undefined, accessToken);
}
export function getAuthHealth(): Promise<HealthResponse> {
  return request("GET", "/healthz", 200, parseHealth);
}

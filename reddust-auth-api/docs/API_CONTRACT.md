# RedDust API Contract — Version 0.1.0 (Local Development)

**Document:** `D:\RedDust\reddust-auth-api\docs\API_CONTRACT.md`  
**Source:** RedDust Step 19C.7 and Appendix L.4; depends on Appendices I (database), J (Google identity), K (tokens), and M (security tests).  
**Status:** **PROPOSED IMPLEMENTATION CONTRACT — NOT PROOF THAT ROUTES EXIST OR PASS TESTS.** Approve decisions below before coding; revise this file and OpenAPI together if implementation requirements change.

## 1. Service boundaries, conventions and security

| Service | Local base URL | Owns | Does **not** own |
|---|---|---|---|
| RedDust Auth API | `http://127.0.0.1:8100` | Seven routes below, Google verification, user/session/call records | WebRTC SDP negotiation |
| RedDust WebRTC Gateway | `http://127.0.0.1:8000` | `POST /offer`, authorized WebRTC signalling/media | Google login, issuing refresh tokens |
| PostgreSQL 18.6 | Server-side only (`127.0.0.1:5432` locally) | Seven Appendix I application tables | Direct access from the phone |

- **API prefix:** `/v1` for application routes; `/healthz` is intentionally unversioned; existing Gateway `/offer` remains unversioned at this stage.
- **Content type:** JSON requests/responses use `Content-Type: application/json`; token-authenticated requests use `Authorization: Bearer <REDDUST_ACCESS_JWT>`. `GET /healthz` has no body.
- **All UUIDs** in JSON/path are canonical UUID strings. Timestamps are UTC RFC 3339 strings (e.g. `2026-10-28T00:00:00Z`). An absent optional object is `null`, not an omitted field, where explicitly shown.
- **Mobile installation ID:** randomly generated, persistently stored app-installation UUID (not a hardware identifier); platform is exactly `android` or `ios`.
- **Do not put** `user_id`, `auth_session_id`, `device_id`, `refresh_token_hash`, database credentials or signing keys in client-supplied identity/authorization fields. Account and session ownership come from verified credentials and server-side database lookups.
- **Production and real-token traffic must use HTTPS.** Loopback HTTP is for local development, with synthetic/test credentials wherever possible. Never transmit real Google/refresh tokens over an unencrypted LAN.
- **Local proposed token policy (to confirm in Appendix K):** RS256 JWT access TTL **900 seconds**, refresh TTL **2,592,000 seconds (30 days)**, JWT issuer `reddust-auth-api`, JWT audiences `reddust-auth-api` and `reddust-gateway`, `kid` identifies the active signing key. Set actual issuer/audiences/TTL in trusted server configuration, not from client input. A service validates its **own** expected audience.
- **Access JWT required claims:** `iss`, `aud`, `sub` (RedDust `app_users.id`), `sid` (`auth_sessions.id`), `iat`, `nbf`, `exp`; signed header contains `alg: RS256` and configured `kid`. Verify signature, algorithm allowlist, issuer, intended audience, time claims, account status and active session; **Google ID tokens are never Gateway bearer tokens**.
- **Refresh token:** cryptographically random opaque secret; return in successful login/refresh response body once; client holds it in secure device storage; `auth_sessions.refresh_token_hash` stores only its derived hash. Never return or log this hash.
- **Security/audit:** no full ID tokens, access JWTs, refresh tokens, SDP, private keys or DB passwords in logs, URLs, error responses or `audit_events.metadata_json`. Audit metadata is short and allowlisted as in Appendix I.
- **Route errors:** documented application errors use `{"detail":{"code":"MACHINE_CODE","message":"Safe public explanation"}}`; standard FastAPI/Pydantic 422 uses `{"detail":[{"loc":["body","field"],"msg":"...","type":"..."}]}` (exact validator message/type may vary). FastAPI's default missing-auth or exception handling may **not** match this proposed error format until explicitly configured. Never send raw database exceptions.
- **Status codes:** 401 = invalid/missing credential (include `WWW-Authenticate: Bearer` for bearer-protected routes); 403 = valid identity/session but forbidden; 404 = missing **or non-owned** call, without revealing ownership; 409 = conflicting state; 422 = request validation failure; 429 = rate limit; 503 = unavailable dependency. Return only codes actually implemented and tested.
- **No automatic completeness:** `/docs` and `/openapi.json` describe **implemented** FastAPI routes. This Markdown records the **target** contract. A route appearing only here is **not implemented**.

### Contract-wide authentication rules

| Route | Google ID token in body? | RedDust Bearer JWT? | Refresh token in body? |
|---|---|---|---|
| `GET /healthz` | No | No | No |
| `POST /v1/auth/google` | **Yes** | No | No |
| `POST /v1/auth/refresh` | No | No (access JWT may be expired) | **Yes** |
| `POST /v1/auth/logout` | No | **Yes** | No |
| `GET /v1/users/me` | No | **Yes** | No |
| `POST /v1/calls` | No | **Yes** | No |
| `POST /v1/calls/{id}/end` | No | **Yes** | No |
| Gateway `POST /offer` | No | **Yes** | No |

## 2. `GET /healthz` — Auth API process health

**Request:** No body, no authentication, no query parameters.  
**Success:** `200 OK`, JSON:

```json
{"status":"ok","service":"reddust-auth-api"}
```

**Errors:** `503` if the application deliberately reports itself unavailable; a refused connection is **not** an HTTP response. Do not include database credentials, customer information or detailed infrastructure. **This is a liveness check, not proof that PostgreSQL or authentication works.**

## 3. `POST /v1/auth/google` — Verify Google and open RedDust session

**Authentication:** No RedDust Bearer JWT; Google ID token must be verified on the server with Appendix J.3 approved audience(s), issuer, signature and expiry. Identity mapping uses `(provider='google', provider_subject=verified_sub)`; never email-only linking. The J.4/J.5 transaction links the user/device atomically. The Appendix K service issues independent RedDust credentials.

**Request:** JSON object with **exactly** these required fields (reject extra fields):

| Field | Type | Rule |
|---|---|---|
| `id_token` | string | Nonempty Google ID token; maximum length 16,384 characters; secret, never log |
| `installation_id` | UUID string | Required persistent app-installation UUID; not a device hardware ID |
| `platform` | enum string | `android` or `ios` |

```json
{
  "id_token":"<GOOGLE_ID_TOKEN_FROM_GOOGLE_SIGN_IN>",
  "installation_id":"70e91b9b-a66a-4c5b-a7ec-14515b0a9028",
  "platform":"android"
}
```

**Success:** `200 OK` for **both first-time and returning** users; `Cache-Control: no-store`:

```json
{
  "user": {
    "id": "0ba779fd-74d9-4d39-92e7-03229b6aa8ba",
    "display_name": "Example User"
  },
  "auth_session_id": "78675bb4-97a6-45d2-a66f-7019bf073237",
  "token_type": "Bearer",
  "access_token": "<REDDUST_RS256_ACCESS_JWT>",
  "expires_in": 900,
  "refresh_token": "<NEW_OPAQUE_RANDOM_REFRESH_TOKEN>",
  "refresh_expires_in": 2592000
}
```

`display_name` may be `null`. `expires_in`/`refresh_expires_in` are seconds, based on issued token/session expiration. Only the hashed refresh credential goes to PostgreSQL; never return `refresh_token_hash`, Google subject or Google raw claims.

| HTTP | Code | When |
|---|---|---|
| 200 | — | Google proof verified, account/device authorized, transaction committed, tokens issued |
| 401 | `INVALID_GOOGLE_TOKEN` | Missing, invalid, expired or wrong-audience Google token (missing body field may be 422) |
| 403 | `ACCOUNT_OR_DEVICE_NOT_ALLOWED` | Disabled account, revoked device or disallowed existing installation |
| 422 | `VALIDATION_ERROR` | Malformed JSON, invalid UUID/platform, missing fields, extra fields |
| 429 | `RATE_LIMITED` | Authentication request rate limit exceeded (once configured) |
| 503 | `AUTH_UNAVAILABLE` | Token-signing or database dependency unavailable |

**Do not mark implemented** until real route code performs all verification, account linking, token creation and failure handling. `app/services/identity.py` by itself does not provide this HTTP endpoint.

## 4. `POST /v1/auth/refresh` — Rotate one refresh credential

**Authentication:** No access JWT required; the submitted **opaque refresh secret** is the credential. Compare its secure hash against a single unrevoked, unexpired `auth_sessions` row; verify account/device status. Rotate **atomically** so two simultaneous requests cannot both consume the same current token.

**Request:** JSON object with exactly one required field:

```json
{"refresh_token":"<CURRENT_OPAQUE_REFRESH_TOKEN>"}
```

`refresh_token`: nonempty string, maximum 512 characters; not in URL/query or logs.

**Success:** `200 OK`, `Cache-Control: no-store`; same underlying auth session, **new** access token and **new** opaque refresh token:

```json
{
  "auth_session_id": "78675bb4-97a6-45d2-a66f-7019bf073237",
  "token_type": "Bearer",
  "access_token": "<NEW_REDDUST_RS256_ACCESS_JWT>",
  "expires_in": 900,
  "refresh_token": "<NEW_OPAQUE_RANDOM_REFRESH_TOKEN>",
  "refresh_expires_in": 2592000
}
```

The old refresh token must immediately stop working after successful rotation. Implement a guarded database update conditioned on the **previous hash and active-session status**; if zero rows update, reject safely.

| HTTP | Code | When |
|---|---|---|
| 200 | — | Current refresh credential consumed exactly once; updated hash committed |
| 401 | `INVALID_REFRESH_TOKEN` | Unknown, expired, revoked, already rotated, or otherwise invalid refresh token |
| 403 | `ACCOUNT_OR_DEVICE_NOT_ALLOWED` | Linked account or installation is disabled/revoked |
| 422 | `VALIDATION_ERROR` | Invalid/missing JSON fields |
| 429 | `RATE_LIMITED` | Rate limit exceeded (once configured) |
| 503 | `AUTH_UNAVAILABLE` | Database/signing unavailable |

**Replay limitation of existing Appendix I schema:** a table retaining **only the current** `refresh_token_hash` can reject an old token, but it cannot reliably *classify* that rejected token as a replay of this particular session after rotation. Implement explicit reuse detection/session-family revocation only after adopting a separately approved token-history/family design; do **not** claim it exists now.

## 5. `POST /v1/auth/logout` — Revoke current RedDust auth session

**Authentication:** RedDust access Bearer JWT required; `sid` and `sub` are verified server-side and must agree with `auth_sessions` ownership. No client-supplied session/user identifiers.

**Request:** Empty JSON object `{}` (or an empty body if explicitly supported by implementation); no other fields.

**Success:** `204 No Content`, empty response body. Server sets `auth_sessions.revoked_at` for the JWT's current active session; future refresh requests fail. If online session-status verification is enforced for every protected request, the revoked JWT also stops authorizing them despite its remaining cryptographic validity.

| HTTP | Code | When |
|---|---|---|
| 204 | — | Current session revoked |
| 401 | `INVALID_ACCESS_TOKEN` | JWT missing/invalid/expired or session already revoked |
| 403 | `ACCOUNT_NOT_ALLOWED` | Verified account is disabled |
| 422 | `VALIDATION_ERROR` | Unexpected request fields or malformed JSON |
| 503 | `AUTH_UNAVAILABLE` | Revocation transaction fails |

## 6. `GET /v1/users/me` — Current account and preferences

**Authentication:** Valid RedDust Bearer JWT, expected audience, active `auth_sessions` row and active `app_users` row; derive account ID from verified `sub`, not request input.

**Request:** No body, no query parameters, no `user_id` parameter.

**Success:** `200 OK`:

```json
{
  "user": {
    "id": "0ba779fd-74d9-4d39-92e7-03229b6aa8ba",
    "display_name": "Example User"
  },
  "preferences": {
    "preferred_persona": null,
    "speaker_default": null
  }
}
```

`preferences` is `null` if no `user_preferences` row exists; when present, each value can be a string or `null`. Never return Google tokens, refresh hashes or other users' data.

| HTTP | Code | When |
|---|---|---|
| 200 | — | Active caller receives own profile |
| 401 | `INVALID_ACCESS_TOKEN` | Missing, invalid or expired JWT, or revoked/expired auth session |
| 403 | `ACCOUNT_NOT_ALLOWED` | Disabled/deleted account |
| 503 | `AUTH_UNAVAILABLE` | Account/session lookup cannot be completed |

## 7. `POST /v1/calls` — Create call for current authorized user

**Authentication:** Valid RedDust Bearer JWT and active, owned auth session; derive `user_id` and `auth_session_id` from trusted JWT + database, never from a request field.

**Request:** Empty JSON object `{}`; reject extra fields such as `user_id`, `auth_session_id`, or `device_id`.

```json
{}
```

**Success:** `201 Created`, response:

```json
{
  "id": "821b0eb5-37be-4e54-8058-075f9e8a9ce1",
  "status": "starting",
  "started_at": "2026-10-28T00:00:00Z",
  "ended_at": null,
  "end_reason": null
}
```

Create `call_sessions` referencing the authenticated user and auth session; rely on Appendix I's `fk_call_auth_same_user` as an additional database safeguard. Client must use the returned call `id` in Gateway `POST /offer`.

| HTTP | Code | When |
|---|---|---|
| 201 | — | Call row created for authenticated caller |
| 401 | `INVALID_ACCESS_TOKEN` | Missing, invalid JWT or inactive session |
| 403 | `ACCOUNT_NOT_ALLOWED` | Caller cannot create calls |
| 422 | `VALIDATION_ERROR` | Body contains prohibited fields |
| 503 | `CALL_SERVICE_UNAVAILABLE` | Database unavailable |

## 8. `POST /v1/calls/{id}/end` — End an owned call

**Authentication:** RedDust Bearer JWT required. `{id}` is a **call UUID**, not a user ID. Use authenticated `sub` and DB ownership to select the call. For a nonexistent **or other-user-owned** call, return the same `404` to avoid revealing another user's records.

**Request path:** `/v1/calls/821b0eb5-37be-4e54-8058-075f9e8a9ce1/end`  
**Request body:** Optional `reason`, one of `user_hangup`, `completed`, `connection_lost`, `error`; defaults to `user_hangup` if omitted. No additional keys.

```json
{"reason":"user_hangup"}
```

**Success:** `200 OK`:

```json
{
  "id": "821b0eb5-37be-4e54-8058-075f9e8a9ce1",
  "status": "ended",
  "started_at": "2026-10-28T00:00:00Z",
  "ended_at": "2026-10-28T00:04:10Z",
  "end_reason": "user_hangup"
}
```

**Idempotency decision:** A repeat request by the **same owner** to end an already-ended call returns `200` with the **existing** persisted end time/reason, without overwriting them. Never mutate an unowned call.

| HTTP | Code | When |
|---|---|---|
| 200 | — | Owned call transitioned to ended, or was already ended |
| 401 | `INVALID_ACCESS_TOKEN` | Missing, invalid JWT or inactive session |
| 403 | `ACCOUNT_NOT_ALLOWED` | Authenticated account is not permitted |
| 404 | `CALL_NOT_FOUND` | UUID not found **or** call belongs to someone else |
| 422 | `VALIDATION_ERROR` | Invalid UUID, unsupported reason, extra body field |
| 503 | `CALL_SERVICE_UNAVAILABLE` | Database unavailable |

## 9. Gateway-only: `POST /offer` — Authorized WebRTC SDP exchange

**Different process:** This is hosted by the **WebRTC Gateway on port 8000**, not in `reddust-auth-api` on port 8100. This is the **target secured contract**; the existing echo Gateway may currently implement only `{sdp, type}` and must be explicitly updated before it is marked compliant.

**Authentication:** `Authorization: Bearer <REDDUST_ACCESS_JWT>`; Gateway verifies RedDust public-key signature/`kid`, issuer, **Gateway audience**, expiry and active session. It must also verify that `call_id` is an eligible active call owned by the authenticated `sub` using a trustworthy server-side authorization path. **Never accept caller-provided `user_id` as evidence**; never treat a Google ID token as a Gateway access token.

**Request:**

```json
{
  "call_id": "821b0eb5-37be-4e54-8058-075f9e8a9ce1",
  "type": "offer",
  "sdp": "<VALID_WEBRTC_SDP_OFFER>"
}
```

- `call_id`: required UUID from `POST /v1/calls`.
- `type`: exactly `offer`.
- `sdp`: nonempty SDP string; apply a documented upper bound (proposed maximum **131,072 UTF-8 bytes**) and validation appropriate to WebRTC signalling. SDP may contain private network information: do not log raw SDP.

**Success:** `200 OK`:

```json
{
  "call_id": "821b0eb5-37be-4e54-8058-075f9e8a9ce1",
  "type": "answer",
  "sdp": "<VALID_WEBRTC_SDP_ANSWER>"
}
```

| HTTP | Code | When |
|---|---|---|
| 200 | — | Authorized caller and eligible call; valid SDP answer generated |
| 401 | `INVALID_ACCESS_TOKEN` | Missing/invalid RedDust Bearer JWT or revoked session |
| 403 | `CALL_NOT_ALLOWED` | Caller lacks authorization to negotiate this call |
| 404 | `CALL_NOT_FOUND` | Unknown or non-owned call where ownership is concealed |
| 409 | `CALL_NOT_ACTIVE` | Owned call is already ended/not eligible for offer |
| 422 | `VALIDATION_ERROR` | Malformed payload/SDP, missing or invalid call UUID |
| 503 | `GATEWAY_UNAVAILABLE` | Negotiation or trusted authorization service unavailable |

The Gateway must **fail closed** if it cannot verify call ownership or current session status; a valid JWT signature alone does not establish that an arbitrary `call_id` is allowed.

## 10. OpenAPI / Swagger and acceptance checklist

**Compare the running services to this target contract; do not mark boxes complete on documentation alone.**

- [ ] Auth API process starts: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8100`.
- [ ] `GET http://127.0.0.1:8100/healthz` responds `200` and **exactly** the safe process-status payload.
- [ ] `http://127.0.0.1:8100/docs` and `/openapi.json` show **only real registered routes**; each matches its documented method, path, schema, Bearer protection and responses.
- [ ] All seven Auth API routes are implemented and exercised against approved local development/test data. **No unimplemented route is described as passing.**
- [ ] Protected routes deny missing/bad/expired Bearer JWTs with `401` (a missing route's `404` does **not** count as proof of authorization).
- [ ] Google ID tokens are verified against approved audiences and mapped by Google `sub`; unique collisions recover without extra users; disabled/revoked identities are denied.
- [ ] Refresh credential is hash-only in DB; rotation is atomic; old token fails; token replay classification is **not** claimed without a history/family design.
- [ ] Logout revokes session; `/users/me` and call actions obtain user identity from JWT + active database session, not from client-supplied `user_id`.
- [ ] Owner can create/end their call; different user cannot access/end it; FK ownership constraints hold.
- [ ] WebRTC Gateway (port 8000) actually implements Bearer and call ownership checks before accepting SDP; Gateway verification is tested separately from Auth API `/docs`.
- [ ] Pydantic **422** shape, error codes, `Cache-Control: no-store` on token responses, status codes and timestamp serialization match this file.
- [ ] Logs/audit/Swagger screenshots are redacted; **no raw credentials or SDP** stored in evidence.
- [ ] Hand over sanitized `GET /healthz` `200`, missing-Bearer `401`, successful login, refresh/logout, owned/unowned calls, Swagger inventory and Gateway evidence to Appendix M.

**Integration boundary:** The React Native phone calls API/Gateway HTTP(S) services; it never talks to PostgreSQL directly. Loopback URLs in this document work only on the Windows development laptop, not from a physical phone.
## Context

See proposal.md for the motivation and `planning/workbench-identity` for the requirements. Today the workbench (`~/dev/plan-workbench`) works like this:

- `auth.py` checks one scrypt password hash, and `Sessions` issues an `itsdangerous` signed cookie holding `{"operator": true, nonce}`, with `SameSite=Strict`, `HttpOnly`, and a 12-hour maximum age (`config.py:39`).
- `require_operator` in `app.py` is the only check on every route. It accepts any valid cookie.
- `workbench serve --host --port` binds through uvicorn. The bind address is known only in the CLI.
- The frontend's sign-in page posts the password to `/api/login`, and `/api/me` answers `{signed_in}`.

The backend already depends on `httpx`. The license must stay compatible with AGPL-3.0.

## Goals / Non-Goals

**Goals:**

- One small, testable OIDC client, tested end to end against a fake provider in the test suite.
- Keep the stateless signed cookie, so that a backend restart, or a `--reload`, keeps people signed in, as it does today.

**Non-Goals:**

- Revoking a session before it expires. A signed cookie cannot be revoked, and the maximum age bounds the exposure.
- Refresh tokens or calls to provider APIs on the person's behalf.
- Single sign-out at the provider. A provider `end_session_endpoint` is used only when it is offered, as a redirect after the local sign-out.

## Decisions

### D1. Our own flow on `httpx` and `joserfc`

The backend performs discovery, the authorization redirect, the code exchange, and ID token validation itself, with `httpx` for HTTP and `joserfc` (BSD-3-Clause) for JWT and JWKS. The JWKS is cached and fetched again when a token names an unknown key id.

- *Alternative:* Authlib's Starlette client. Rejected: it brings its own session middleware and cookie, which would sit beside ours, and its flow is harder to drive from a fake provider in tests. `joserfc` comes from the same author, so the cryptography is the same.

### D2. Two cookies with different `SameSite` values

- **Sign-in attempt.** `workbench_login` is a signed cookie with a 10-minute maximum age, `SameSite=Lax`, and `HttpOnly`. It holds `state`, `nonce`, the PKCE verifier, and the return path. It must be `Lax`, because the provider's redirect back is a cross-site top-level `GET`, and a `Strict` cookie would not be sent with it. The callback deletes it.
- **Session.** `workbench_session` stays `SameSite=Strict`. It holds `{iss, sub, name, email, roles, mode}`, signed with the existing secret key.

The return path is accepted only when it starts with a single `/` and is not `//`, so that the person cannot be sent to another site.

### D3. One `Identity`, and dependencies for roles

`require_operator` becomes `current_identity`, a FastAPI dependency that returns an `Identity`, plus `require_role("approver")`. Every router keeps one dependency, so no route can be left without a check. Routes that record an actor take `Identity` as a parameter, which is how "never from the request body" is enforced in code.

Roles today:

| Role | Routes |
|---|---|
| `planner` | every existing route |
| `approver` | none yet. Changes `plan-approvals` and `workbench-worker-sessions` add them. |

A test asserts that every route declares a check, so a new route cannot ship open.

### D4. Local mode is decided in the CLI

`Config` gains `oidc_issuer`, `oidc_client_id`, `oidc_client_secret` (with a `_FILE` variant), `oidc_redirect_url`, `oidc_roles_claim` (default `groups`), `oidc_planner_group`, `oidc_approver_group`, and `allow_local_mode`. With no issuer, the app keeps `/api/login` and issues a session with `iss=local, sub=operator`. `workbench serve` knows the bind host, so it refuses to start in local mode on an address that is not loopback, unless `WORKBENCH_ALLOW_LOCAL_MODE=1` is set.

### D5. `/api/me` becomes the identity

`/api/me` answers `{signed_in, mode: "oidc" | "local", identity: {name, email, roles}}`. In OIDC mode, the frontend's sign-in page becomes a *Sign in* link to `/api/auth/login?next=<path>`. In local mode, it keeps the password form. The top bar shows the name and a *Sign out* control.

## Risks / Trade-offs

- [A stolen session cookie works until it expires] → It is `HttpOnly`, `Strict`, and `Secure` behind HTTPS, and the maximum age stays 12 hours. Revocation would need server-side sessions, which can be added later behind the same `Identity` dependency.
- [Group names differ between providers] → Both the claim name and the group names are configuration, and the operator guide shows examples for common providers.
- [Clock skew fails ID token expiry checks] → Allow 60 s of leeway on `exp`, `iat`, and `nbf`.
- [A local-mode workbench exposed by mistake] → The CLI refuses a bind address that is not loopback, unless local mode is allowed explicitly.

## Migration Plan

1. Deploy with no issuer configured. Local mode behaves as today's password sign-in, now with both roles.
2. Register the workbench as a client at the provider, with the redirect URL `<base>/api/auth/callback`, then configure the issuer, client, and groups, and restart. Existing cookies lack an identity, so they no longer count, and everyone signs in once more.

Rollback: unset the issuer and restart, which returns to local mode.

## Open Questions

- Which provider the team uses first (for example Keycloak, Authentik, Google, or GitHub through Dex). The flow is the same for each. The provider only decides the example values in the operator guide.

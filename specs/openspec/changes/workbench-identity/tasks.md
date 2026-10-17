The work is in the plan workbench (`~/dev/plan-workbench`). Every task ends with `uv run pytest` and, for frontend tasks, `npm run check` and `npm test` in `frontend/` passing.

## 1. Identity and roles

- [ ] 1.1 Add the OIDC settings and `allow_local_mode` to `Config.from_env` (design D4), with `WORKBENCH_OIDC_CLIENT_SECRET_FILE` read like the other secrets. Verify with config tests: the defaults, a partial OIDC setup rejected with the missing variable named, and a secret file.
- [ ] 1.2 Add `Identity` and the session cookie with `{iss, sub, name, email, roles, mode}` (design D2). Replace `require_operator` with `current_identity` and `require_role`. Verify with tests: a session from before this change no longer counts, an expired cookie fails, and a test lists every route and fails when one declares no check.
- [ ] 1.3 Map the roles claim to `planner` and `approver`, where the approver group grants both and neither group refuses sign-in. Verify with table tests for each `planning/workbench-identity` role scenario.

## 2. OpenID Connect flow

- [ ] 2.1 Add `joserfc` to the dependencies, and check that its license is compatible with AGPL-3.0. Add a fake provider for the tests: a discovery document, a JWKS with rotating keys, and authorization and token endpoints, all served through the `httpx` mock transport. Verify that the fake signs a token that `joserfc` validates.
- [ ] 2.2 Add `/api/auth/login`, with `state`, `nonce`, the PKCE S256 challenge, the `workbench_login` cookie, and the `next` check. Add `/api/auth/callback`, with the code exchange and validation of `state`, signature, `iss`, `aud`, `exp` (60 s leeway), and `nonce`. Verify with tests for a successful sign-in, each refused check, an expired attempt, an unknown key id that triggers a JWKS refresh, and `next=https://evil.example/` landing on `/`.
- [ ] 2.3 Make `/api/logout` end the session and redirect to the provider's `end_session_endpoint` when it is offered. Make `/api/me` answer the identity (design D5). Verify with tests for both, and a test that no response body or header carries a provider token.

## 3. Local mode

- [ ] 3.1 Keep the password sign-in when no issuer is set, issuing `iss=local, sub=operator` with both roles. Make `workbench serve` refuse a non-loopback `--host` in local mode unless `WORKBENCH_ALLOW_LOCAL_MODE=1`. Verify with tests for local sign-in, the refusal (exit code and message), and the explicit override.

## 4. Frontend

- [ ] 4.1 Show the *Sign in* link in OIDC mode, the password form in local mode, and the person's name and a *Sign out* control in the top bar. Add a `can(role)` helper that later changes use to hide approver actions. Verify with component tests for both modes and the no-role message, then check both modes in the workbench Firefox on `scripts/dev.sh`.

## 5. Documentation and an end-to-end check

- [ ] 5.1 Update `docs/operator-guide.md`: provider client registration, the redirect URL, every variable, groups, and local mode. Verify that each variable named in design D4 appears in the guide.
- [ ] 5.2 Run the workbench against a real OIDC provider in a container (for example Keycloak or Dex), with one planner user and one approver user. Record in `verification.md` how each user signs in, what `/api/me` returns, and that a user with no group is refused.

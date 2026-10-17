# Verification

Work is in `~/dev/plan-workbench` on `main`, commits `b1c0541` to `7a91bfc`. `uv run pytest` passes 146 tests, with 0 skipped. In `frontend/`, `npm run check` reports 0 errors and 0 warnings, and `npm test` passes 52.

## Real provider check (task 5.2)

Dex v2.41.1 ran in a container (`ghcr.io/dexidp/dex:v2.41.1`) with its mock connector, which signs in the user Kilgore Trout with the groups `authors` and `admins`. The workbench ran on port 8799 with `WORKBENCH_OIDC_SCOPES="openid profile email groups"`. Everything was driven in the workbench Firefox.

| Planner / approver groups | Result of signing in |
|---|---|
| `readers` / `authors` | Redirected back to `#/new`. `/api/me` reported `roles: ["planner", "approver"]`, `id: "http://127.0.0.1:5556/dex|Cg0wLTM4NS0yODA4OS0wEgRtb2Nr"`. The top bar showed "Kilgore Trout" and "Sign out". |
| `authors` / `admins` | `roles: ["planner"]`. |
| `nobody-group` / `admins` | Refused. The page said "You have no role in the plan workbench…". |

The third run first exposed a bug: a refused sign-in left the person's earlier session in place, so they still appeared signed in. The callback now deletes the session cookie on every refusal. `test_a_refused_sign_in_ends_an_earlier_session` covers it, and fails with the fix removed.

Local mode was checked in the same Firefox: the password form, the note "Local mode: one shared password", sign-in, the name "Local operator" with **Sign out**, and sign-out returning to the form, with no console errors.

## Deviations

- `WORKBENCH_OIDC_SCOPES` was added: Dex, like Okta, returns `groups` only for the `groups` scope.
- `GET /api/auth/mode` is public, so the sign-in page knows which form to show before anyone is signed in.
- The approver role guards no existing route yet. `plan-approvals` and `workbench-worker-sessions` add those routes.

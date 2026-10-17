## Why

The plan workbench has one shared operator password (`workbench hash-password`) and a signed session cookie. It cannot tell people apart. Change `plan-approvals` makes approving a story the act that sends it to agents, and it records who approved each story in the tracker. That needs a real identity for each person, from the identity provider the team already uses. A shared password cannot give it.

## What Changes

- The workbench signs people in through **OpenID Connect** (authorization code flow with PKCE). Any standards-compliant provider works; the issuer, client id, and client secret are configuration.
- The backend keeps the person's identity in its own session: the issuer and subject (`iss`, `sub`) as the stable key, plus the display name and email for display. The browser holds only the workbench's own cookie, as today. No provider token reaches the browser.
- **Roles.** The workbench maps provider claims (for example a group) to two roles:
  - `planner`: may plan, edit, and sync, and may run planning sessions.
  - `approver`: everything `planner` may do, and also approve stories, release them, pull them back, cancel them, and supersede them.
  The claim and the group names are configuration.
- Every action that changes what agents will do records the person who did it: approve, pull back, cancel, supersede, and sync. Change `plan-approvals` stores these records. This change provides the identity.
- The identity is exposed to the rest of the backend as one object (`iss`, `sub`, name, email, roles), so later surfaces (worker attach, steering) can reuse it.
- **BREAKING:** the shared-password login is removed once OIDC is configured. A single-person local mode stays for development: with no issuer configured, the workbench keeps today's password login and treats that person as a local `approver`. Records made in that mode name the local identity, never a provider identity.

## Capabilities

### New Capabilities
- `planning/workbench-identity`: OIDC sign-in and sign-out, the backend session and what it holds, the local development mode, the identity object, and the mapping from claims to the `planner` and `approver` roles.

### Modified Capabilities

None. This store has no archived specs yet. This change replaces the operator sign-in that change `plan-to-tracker-dag` gives the workbench (`planning/plan-workbench`).

## Impact

- Workbench backend (`src/workbench/`): `auth.py` and the sign-in routes in `app.py` gain the OIDC flow and roles. `require_operator` becomes a check for a role. New configuration variables are the issuer, client id, client secret, redirect URL, roles claim, and group names.
- Workbench frontend: the sign-in page becomes a redirect to the provider, and the person's name is shown in the top bar.
- A new dependency: an OIDC client library for Python. Its license must be compatible with AGPL-3.0.
- `docs/operator-guide.md`: provider setup, and the local mode for development.
- Out of scope:
  - running a provider; the team brings its own;
  - per-project permissions; roles apply to every project;
  - identity for Sortie or `acp-broker`; their tokens do not change.

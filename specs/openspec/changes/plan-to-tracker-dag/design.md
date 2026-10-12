## Context

See proposal.md for the motivation and specs/ for the requirements. This design starts from what already exists:

- **Sortie fork, branch `prototype/huly-tracker`.** It has a Huly tracker adapter that reads issues over the transactor REST API (`find-all` and `tx`), and reads descriptions from the collaborator `getContent` RPC. It can't create issues or write descriptions yet.
- **Sortie's tracker contract** (`internal/domain/tracker.go`) has no write operations beyond status, comments, and labels. It already uses one optional interface, `BlockerReader`, which each adapter declares through `registry.TrackerMeta`.
- **Sortie's HTTP API** (`internal/server`) serves only `/api/v1/state`, `/api/v1/refresh`, and the issue detail endpoint. Change `sortie-session-control` adds authentication for control calls.
- **Change `acp-broker`** gives an ACP session an authenticated HTTP transport (Server-Sent Events plus `POST`), with replay for late viewers and a session registry. The broker can run on its own, without Sortie.
- **The viewer prototype** (`~/dev/huly-dag-prototype`) is plain HTML, CSS, and JavaScript on synthetic data. Its layout, card, and edge rules are the reference for the graph pane. `PRODUCT.md` and `DESIGN.md` in that repo hold its product and visual decisions.
- **OpenSpec 1.13** supports custom schemas (`openspec schema fork`), whose artifacts declare `requires:`. It has no dependencies between changes.

Constraints:
- Sortie changes stay additive and isolated, so they rebase onto upstream: Go standard library, no CGo, generic names in core, and adapter-specific logic only in adapter packages.
- The workbench uses FastAPI and Vite. It never calls a tracker directly.

## Goals / Non-Goals

**Goals:**
- One parser and validator for the plan, in Sortie. The workbench never reimplements it.
- A deployment that runs on one host now and can split across hosts later without a redesign.
- A first end-to-end path on Huly: chat, then breakdown, then graph, then sync, then dispatch, then live badges.

**Non-Goals:**
- Accounts for several people in the workbench. One operator signs in. Roles and shared editing come later.
- A layout engine with crossing reduction. The prototype's layered placement is the starting point.
- Write capabilities for adapters other than Huly. This design only checks that the capability model fits GitHub, Jira, and Linear.

## Decisions

### D1. Sortie owns the plan parser, and clients send it the files

A new package `internal/plan` in the Sortie fork parses `plan.md` and each `breakdown.md`, validates them, builds the combined graph, and computes a sync preview against the tracker. Nothing else parses the plan.

Sortie and the spec store may sit on different hosts, so the HTTP endpoints do not read a path on Sortie's disk. A client sends a **store snapshot** instead: `plan.md`, each change's `breakdown.md`, and the requirement names from each change's specs. Sortie returns the parsed graph and every validation error (`POST /api/v1/plan/parse`), or a preview for a sync. The CLI `sortie plan sync --store <path>` builds the same snapshot from a local path and calls the same code.

The snapshot has a digest. A preview records the snapshot digest and a digest of the plan-keyed tracker state it read. An apply carries the preview id, and Sortie recomputes both digests before writing. A mismatch is the conflict the plan-sync spec requires.

*Alternatives:*
- A Python parser in the workbench. It would be a second implementation that drifts from Sortie's, and validation results would differ between the graph and the sync.
- Sortie reading a configured store path. This ties Sortie to the store's host.
- The workbench calling the `sortie` binary. This ties the workbench to Sortie's host and config. The user rejected that.

### D2. Breakdown as a forked OpenSpec schema, with approval by digest

The store adds schema `spec-driven-planned`, forked from `spec-driven`, with one new artifact, `breakdown` (`breakdown.md`). It requires `proposal`, `specs`, and `design`, and `tasks` now requires `breakdown`. `tasks.md` stays the implementation checklist, grouped under deliverable ids. A change opts in by setting `schema: spec-driven-planned` in its `.openspec.yaml`. The artifact's instruction text carries the deliverable format from the breakdown spec, so `openspec instructions breakdown` teaches the agent the format.

Approval is front matter: `status: approved` plus `approved_digest`, a hash of the normalized deliverable sections. The parser treats a breakdown as `draft` whenever the digest does not match. So any edit after approval returns it to draft, and no tool has to rewrite the file. The workbench's Approve action writes both fields. The planning agent's instructions forbid it from setting them.

*Alternatives:*
- YAML or JSON breakdowns. Easier to parse, worse to review in a pull request, and the user reviews plans in git.
- Reusing `tasks.md` with dependency annotations, as spec-kit does. It mixes the build order with the coding checklist, and OpenSpec's apply flow already owns `tasks.md`.

### D3. The plan key is stored however each adapter can store it reliably

Each adapter declares a `PlanKeyStorage` in `TrackerMeta`, and implements find-by-plan-key on top of it.

- **Huly:**
  - A custom attribute `sortiePlanKey` (a string) on `tracker:class:Issue`, created through the API the first time it's needed. Huly's own settings UI creates class attributes the same way, so this needs no Huly fork.
  - The adapter finds an issue with `find-all` on that attribute.
  - Epic and Story are task types the operator creates in the project type. They are named in config (`huly.epic_type`, `huly.story_type`). The adapter resolves them at construction and fails when they are missing.
- **Trackers with custom fields (Jira, Linear):** a custom field, by the same pattern.
- **Trackers without custom fields (GitHub, Gitea):**
  - A one-line marker at the end of the body: `<!-- sortie-plan-key: billing/invoice -->`.
  - The adapter finds an issue with the tracker's search.
  - Sync owns the body of plan-keyed issues, so the marker survives.

*Alternatives:*
- A label per plan key. This floods the label catalog, and Sortie already gives labels meaning (stage labels, the parking label).
- A body marker on Huly. Finding an issue by key would mean one collaborator call per issue.

### D4. Huly write path

- **Creating an issue** follows Huly's own importer:
  1. Increment the project's `sequence` with `$inc` and `retrieve: true` to get the issue number.
  2. Build the identifier.
  3. Compute a rank after the last issue's rank, ported from `@hcengineering/rank`.
  4. Send `TxCreateDoc` in the parent's `subIssues` collection, or under `tracker:ids:NoParent`.
- **The description** is written with the collaborator `createContent` RPC, then referenced from the issue. The body is converted to markup with the existing `markup` package plus a small Markdown writer for headings, lists, paragraphs, and code. Huly renders it, and nothing reads it back as structure.
- **Dependencies** are added to and removed from `blockedBy` with `$push` and `$pull`. Changing the parent updates `attachedTo` and `parents`.

### D5. Capability interfaces in the domain package

`internal/domain` gains four interfaces, each with one or two methods:
- `IssueCreator`;
- `IssueUpdater`;
- `IssueParenter`;
- `DependencyLinker`.

It also gains a `PlanKeyFinder`. `registry.TrackerMeta` gains a `WriteCapabilities` set and `PlanKeyStorage`. The registry checks at startup that the declared set matches the implemented interfaces, so an adapter cannot claim a capability it lacks. This copies `BlockerReader` and `BlockerSource`, so the rest of the codebase learns no new pattern.

*Alternative:* one large `TrackerWriter` interface. Trackers differ one capability at a time, as GitLab Community Edition with no dependencies shows, so one interface would force stubs.

### D6. Sortie endpoints

All four endpoints sit beside the existing API and use the control authentication from change `sortie-session-control`:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/plan/parse` | Takes a snapshot. Returns the graph and the validation errors. Never touches the tracker. |
| `POST /api/v1/plan/sync` | Takes a snapshot. `apply: false` returns a preview with an id. `apply: true` takes the preview id. |
| `GET /api/v1/plan/graph` | Returns the plan-keyed issues, parents, and edges from the tracker, joined with runtime state from the orchestrator snapshot. |
| `GET /api/v1/plan/capabilities` | Returns the configured adapter's declared write capabilities. |

An apply runs the writes in dependency order:
1. create epics;
2. create stories;
3. set parents;
4. update fields;
5. add relations;
6. remove relations.

It stops at the first failure and reports progress, which the plan-sync spec requires. Two applies cannot run at once: a mutex covers the apply, and a second caller gets `409`.

### D7. Workbench architecture

A new repository, `~/dev/plan-workbench`, is seeded from the prototype's `PRODUCT.md`, `DESIGN.md`, and graph code. The prototype stays as the design reference.

```
 browser (Vite build)                     FastAPI backend                      services
 +-----------------------+   SSE + REST   +------------------------------+
 | graph pane (60%)      | <------------> | /api/graph   merged graph    | --> Sortie /api/v1/plan/*
 | chat pane (40%)       |                | /api/events  SSE: graph,     | --> Sortie /api/v1/state
 |  context card on top  |                |              validation      |
 +-----------------------+                | /api/session relay           | <-> acp-broker HTTP
                                          | /api/sync    preview/apply   |
                                          | watcher on store/openspec/   | <-- spec store (local fs)
                                          +------------------------------+
```

- **Backend.**
  - FastAPI serves the built frontend and a small JSON and SSE API. It holds the Sortie and broker tokens.
  - It watches `openspec/` with `watchfiles`. On a change it debounces for 300 ms, builds a snapshot, calls `/plan/parse`, merges the result with `/plan/graph` by plan key (draft, synced, orphaned), and pushes the merged graph over SSE. It polls runtime state every five seconds.
  - Sign-in is one operator password from configuration, with a signed `HttpOnly` session cookie.
  - Dependencies are FastAPI, uvicorn, httpx, watchfiles, and itsdangerous.
- **Frontend.**
  - Vite with TypeScript and **Svelte 5**. Svelte fits a custom SVG and absolutely positioned layout better than a component kit does, its output is small, and Huly uses Svelte, if code ever moves between the two.
  - The layout code is ported from the prototype as a framework-free TypeScript module, so it can be tested on its own.
  - No component library. The design system is the prototype's `DESIGN.md` tokens as CSS variables.
  - *Alternatives:* React with React Flow, whose free-form canvas fights the fixed depth columns; or no framework at all, which is fine for the graph but costly for the streaming chat and its state.
- **Detail panel in the 60/40 layout.** The prototype's 360px side panel moves to the top of the chat pane as a collapsible **context card**. Selecting a node fills the card with its details and attaches the node to the next message. With nothing selected, the card shows ready, active, and unplanned lists. This keeps the graph at 60% and joins "what I'm looking at" with "what I'm asking about". Live mode on the workbench refines it.

### D8. Planning session lifecycle

- The workbench backend starts `acp-broker` in standalone mode, one process per planning session, with:
  - the configured agent command (OpenCode by default);
  - working directory set to the spec store;
  - the HTTP transport bound to localhost.
- The backend finds the session through the broker registry and relays its SSE stream and `POST` commands to the browser under the operator's cookie, so the broker token never reaches the browser.
- The session prompt names the store, the planning schema, and the write limit to `openspec/`. The prompt is a file in the workbench repo, so it can be revised without code changes.
- A reload reattaches through the broker's replay. Ending a session stops the broker process.
- Selected nodes are added to the next prompt as a short structured block: plan keys, titles, kinds, and identifiers.

## Risks / Trade-offs

- [Huly's issue creation needs a client-side sequence and rank, the same work its UI and importer do. A mistake gives duplicate numbers or a broken order.] → Use `$inc` with `retrieve`, which the transactor applies atomically, so numbers can't collide. Port the rank function with its tests. Cover creation in the env-gated Huly integration test.
- [Creating a custom attribute on Huly's Issue class changes the workspace model.] → Create it only on the first write. Name it clearly as Sortie's. Document how to remove it in the Huly adapter notes. Check that it doesn't need a workspace upgrade on v0.7.426.
- [Snapshots grow with the store, and every file change sends one to Sortie.] → Snapshots hold only `plan.md`, breakdowns, and requirement names, which is kilobytes. The backend debounces. When it matters, the backend sends only changed breakdowns and Sortie caches parsed changes by digest.
- [The agent edits files while a sync preview is open.] → The apply re-checks the snapshot digest and refuses when it is stale. The workbench then offers a fresh preview.
- [People edit synced issues in the tracker (titles, parents, dependencies) and the next sync reverts them.] → The preview lists every revert, so nothing changes silently. Syncing back into the breakdown is out of scope and recorded as follow-up work.
- [Dependency support differs across trackers.] → A tracker without it does not declare **link dependency**, and sync refuses up front. GitHub has issue dependencies and sub-issues, Jira has issue links, and Linear has relations. Each maps to the four capabilities without changing the model.
- [Svelte is a new frontend stack for this platform.] → It is limited to the workbench. The layout logic is framework-free TypeScript, so changing UI frameworks later costs only the components.
- [A planning agent with shell access in the store could write outside `openspec/` or call a tracker API directly.] → The prompt sets the limit, and the broker's permission requests show every tool call in the chat. A sandbox is change `execution-environment`'s job and is not relied on here.

## Migration Plan

1. In the store, fork the schema and write `openspec/plan.md` covering the active changes. Existing changes switch to the planning schema one at a time. A change that hasn't switched is unplanned and the workbench marks it that way.
2. In the Sortie fork, build on `prototype/huly-tracker`:
   1. capability interfaces and the registry check;
   2. `internal/plan`;
   3. the CLI and the endpoints;
   4. the Huly write path.

   Other adapters are untouched.
3. Create the workbench repo. Point it at a local Sortie, the broker, and the store.
4. Rollback: stop the workbench and stop running syncs. Issues already created stay as ordinary tracker issues that Sortie dispatches like any other. The custom attribute stays and is harmless.

## Open Questions

- Should the epic-level graph also show changes that are not in `plan.md` yet, as unplaced drafts? It is a display choice, settled in live mode.
- Should the workbench ever become a Sortie-served page once the design settles? Nothing in this design depends on the answer.

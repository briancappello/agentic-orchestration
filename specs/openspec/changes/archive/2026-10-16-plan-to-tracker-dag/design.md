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
- One validator for the plan, run where the plan is written. Schemas, not parser code, define the format between components.
- A deployment that runs on one host now and can split across hosts later without a redesign.
- A first end-to-end path on Huly: chat, then breakdown, then graph, then sync, then dispatch, then live badges.

**Non-Goals:**
- Accounts for several people in the workbench. One operator signs in. Roles and shared editing come later.
- A layout engine with crossing reduction. The prototype's layered placement is the starting point.
- Write capabilities for adapters other than Huly. This design only checks that the capability model fits GitHub, Jira, and Linear.

## Decisions

### D1. Plan files are data, validated where they are written

The plan is YAML checked against published JSON Schemas, not markdown that one service's parser interprets.

- **Contract.** The spec store holds three JSON Schemas under `openspec/schemas/planning/`:
  - `breakdown.schema.json`;
  - `plan.schema.json`;
  - `plan-graph.schema.json`, the validated graph that leaves the store.

  Each carries a `schema_version`. The schemas are the contract. No parser's code is.
- **Validator.** A small Python package, `planlib`, is the plan validator. It offers a CLI (`planlib validate`, `planlib graph`) and a library API. It lives in the workbench repo and is installed into the planning session's environment. It runs in three steps:
  1. **Schema check** with `jsonschema`, rejecting unknown fields.
  2. **Requirement names** for `covers`, read from `openspec show <change> --type change --json`. OpenSpec stays the authority on its own spec format, and nothing scrapes spec markdown.
  3. **Graph checks** with `networkx`. `find_cycle` reports each cycle as its member list, the plan's transitive reachability checks cross-change edges, and refs are resolved against the set of known keys.

  It collects every error and outputs either the error list or the graph document.
- **Where checks run.**
  - The planning agent runs `planlib validate` after each write and fixes errors in the same session.
  - The workbench backend calls the library on every file change.
  - Sortie does not validate the plan. It checks only that the graph document is well formed: a supported version, a match with the graph schema, and edges that name nodes in the document. A minimal Go struct decode with version gating does this. Sortie needs no JSON Schema library and gains no dependency.
- **Digest.** The graph document carries a digest of the source files. A preview records that digest and a digest of the plan-keyed tracker state. An apply recomputes both and refuses on a mismatch.

*Alternatives:*
- Markdown parsed by Sortie, the first design. It was rejected as brittle: the format was defined only by Go code, and errors surfaced after the fact in another service.
- Validation in Go inside Sortie, called by the workbench. The planning agent would then need Sortie running to check its own files.
- A hand-written DAG check instead of `networkx`. That is about forty lines, and remains an option if the dependency is unwanted. `networkx` also gives `topological_generations`, which the workbench uses for column depth.

### D2. Breakdown artifact in a forked OpenSpec schema

The store adds schema `spec-driven-planned`, forked from `spec-driven`, with one new artifact, `breakdown`, which generates `breakdown.yaml`.
- It requires `specs` and `design`.
- `tasks` now requires `breakdown`. `tasks.md` stays the implementation checklist, grouped under deliverable ids.
- A change opts in through `schema: spec-driven-planned` in its `.openspec.yaml`.

A scratch test with OpenSpec 1.13 confirmed that a YAML artifact works:
- `schema validate` accepts it;
- `status` tracks it;
- `instructions breakdown` serves its template.

The artifact's instruction tells the agent to write against `breakdown.schema.json` and to run `planlib validate`.

Approval uses two top-level fields: `status: approved` and `approved_digest`, a hash of the canonical JSON of `deliverables`. `planlib` reads a breakdown as `draft` whenever the digest does not match. So any edit after approval returns it to draft, and no tool has to rewrite the file. The workbench's Approve action writes both fields. The planning agent's instructions forbid it from setting them.

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

All three endpoints sit beside the existing API and use the control authentication from change `sortie-session-control`:

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/plan/sync` | Takes a validated graph document. `apply: false` returns a preview with an id. `apply: true` takes the preview id. |
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
  - It watches `openspec/` with `watchfiles`. On a change it debounces for 300 ms, runs `planlib`, merges the result with `/plan/graph` by plan key (draft, synced, orphaned), and pushes the merged graph over SSE. It polls runtime state every five seconds.
  - Sign-in is one operator password from configuration, with a signed `HttpOnly` session cookie.
  - Dependencies are FastAPI, uvicorn, httpx, watchfiles, itsdangerous, and, through `planlib`, PyYAML, jsonschema, and networkx.
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
- [`openspec show --json` output changes between OpenSpec versions, and `covers` checks break.] → `planlib` reads only requirement names from it, pins the OpenSpec version it was tested against, and reports a clear error instead of a false pass.
- [The schemas and `planlib` drift, or two clients run different schema versions.] → The schemas live in the store and `planlib` loads them from there. Each document carries `schema_version`, and every reader refuses versions it doesn't support.
- [The agent edits files while a sync preview is open.] → The apply re-checks the graph's source digest and refuses when it is stale. The workbench then offers a fresh preview.
- [People edit synced issues in the tracker (titles, parents, dependencies) and the next sync reverts them.] → The preview lists every revert, so nothing changes silently. Syncing back into the breakdown is out of scope and recorded as follow-up work.
- [Dependency support differs across trackers.] → A tracker without it does not declare **link dependency**, and sync refuses up front. GitHub has issue dependencies and sub-issues, Jira has issue links, and Linear has relations. Each maps to the four capabilities without changing the model.
- [Svelte is a new frontend stack for this platform.] → It is limited to the workbench. The layout logic is framework-free TypeScript, so changing UI frameworks later costs only the components.
- [A planning agent with shell access in the store could write outside `openspec/` or call a tracker API directly.] → The prompt sets the limit, and the broker's permission requests show every tool call in the chat. A sandbox is change `execution-environment`'s job and is not relied on here.

## Migration Plan

1. In the store, fork the schema and add the planning JSON Schemas, and write `openspec/plan.yaml` covering the active changes. Existing changes switch to the planning schema one at a time. A change that hasn't switched is unplanned and the workbench marks it that way.
2. In the Sortie fork, build on `prototype/huly-tracker`:
   1. capability interfaces and the registry check;
   2. `internal/plan`, which decodes and version-checks the graph document and computes the preview and apply;
   3. the CLI and the endpoints;
   4. the Huly write path.

   Other adapters are untouched.
3. Create the workbench repo with `planlib` first, so the planning session can validate before the UI exists. Point it at a local Sortie, the broker, and the store.
4. Rollback: stop the workbench and stop running syncs. Issues already created stay as ordinary tracker issues that Sortie dispatches like any other. The custom attribute stays and is harmless.

## Open Questions

- Should the epic-level graph also show changes that are not in `plan.yaml` yet, as unplaced drafts? It is a display choice, settled in live mode.
- Should the workbench ever become a Sortie-served page once the design settles? Nothing in this design depends on the answer.

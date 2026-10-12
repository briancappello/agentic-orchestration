The work spans three repositories:

- **The spec store** (`~/dev/agent-platform-specs`).
- **The Sortie fork** (`~/dev/sortie`). Work starts from branch `prototype/huly-tracker`. Every Sortie task ends with `make test` and `make lint` passing.
- **The workbench** (`~/dev/plan-workbench`). Every workbench task ends with the backend tests (`pytest`) and the frontend checks (`npm run check`, `npm test`) passing.

## 1. Planning formats in the spec store

- [x] 1.1 Add `openspec/schemas/planning/breakdown.schema.json`, `plan.schema.json`, and `plan-graph.schema.json` at `schema_version` 1, as the breakdown, plan-of-plans, and plan-validator specs define them. Verify with sample documents: a valid one passes, and one with an unknown field, a bad `kind`, or a missing `acceptance_criteria` fails.
- [x] 1.2 Fork `spec-driven` into `spec-driven-planned`. Add the `breakdown` artifact (generates `breakdown.yaml`, requires `specs` and `design`), make `tasks` require it, and write the artifact's template and its instruction, which points to the schema and to `planlib validate`. Verify that `openspec schema validate spec-driven-planned` passes, and that a scratch change shows `breakdown` in `openspec status`.

## 2. planlib validator (workbench repo)

- [x] 2.1 Create `~/dev/plan-workbench` with a Python project for `planlib`, using PyYAML, jsonschema, and networkx. Load the schemas from the store path given at run time, and refuse a newer `schema_version` with a message that names both versions. Verify with tests for loading, a version mismatch, and unknown fields.
- [x] 2.2 Read requirement names for `covers` from `openspec show <change> --type change --json`. Pin the tested OpenSpec version, and fail clearly when the output shape is unexpected. Verify against a fixture captured from OpenSpec 1.13, and against a real change in the store.
- [x] 2.3 Implement the graph checks:
  - unique ids;
  - refs that resolve;
  - changes in the plan that exist;
  - no cycles in the epic graph or the deliverable graph, each reported with all its members;
  - dependencies between changes that agree with the plan;
  - `covers` refs that exist.

  Every error is collected. Verify with one test for each scenario in the plan-validator spec, including several problems in one run.
- [x] 2.4 Implement approval reading (`approved_digest` over the canonical JSON of `deliverables`) and an `approve` function that writes both fields. Verify with tests: approve, then edit, reads as draft; approve again reads as approved.
- [x] 2.5 Output the plan-graph document (nodes, parents, blocking edges, source digest) and the column depth from `topological_generations`. Add the CLI commands `planlib validate` and `planlib graph`. Verify that the output matches `plan-graph.schema.json`, and that the CLI exits non-zero with the errors listed when the plan is invalid.
- [x] 2.6 Write `openspec/plan.yaml` and a `breakdown.yaml` for this change (`plan-to-tracker-dag`) in the store, as the first real plan. Verify that `planlib validate` passes on the store.

## 3. Sortie: tracker write capabilities

- [x] 3.1 Add the optional interfaces `IssueCreator`, `IssueUpdater`, `IssueParenter`, `DependencyLinker`, and `PlanKeyFinder`, and the `tracker_unsupported_operation` error kind, to `internal/domain`. Add `WriteCapabilities` and `PlanKeyStorage` to `registry.TrackerMeta`, with a check at registration that a declared capability is implemented. Verify with registry tests: a declared but unimplemented capability is rejected, and every existing adapter still registers with no write capabilities.
- [x] 3.2 Update the tracker-contract section and the adapter-concepts doc for the new capabilities. Verify with `make lint-docs`.

## 4. Sortie: Huly write path

- [x] 4.1 Resolve the Epic and Story task types from config (`huly.epic_type`, `huly.story_type`) when the adapter is constructed. Fail with the project's task type names when either is missing. Verify with fake-RPC tests and the env-gated integration test.
- [x] 4.2 Ensure the `sortiePlanKey` attribute exists on `tracker:class:Issue`, creating it on the first write, and implement `PlanKeyFinder` with it. Verify against the local Huly (v0.7.426) that the attribute is created once, survives a rename in the UI, and finds the issue. Record how to remove it in the Huly adapter notes.
- [x] 4.3 Implement `IssueCreator`:
  - get the issue number with a `$inc` on the sequence using `retrieve: true`;
  - compute the rank with a port of Huly's rank function and its tests;
  - store the description through collaborator `createContent`;
  - create the issue in the parent's `subIssues` collection, or under `NoParent`.

  Verify that unit tests cover the rank and the transaction shape, and that the integration test creates an epic and a story that Huly's UI shows nested, with the right type and description.
- [x] 4.4 Implement `IssueUpdater`, `IssueParenter` (`attachedTo` and `parents`), and `DependencyLinker` (`blockedBy` with `$push` and `$pull`, idempotent). Declare all four capabilities. Verify with fake-RPC tests for linking twice and unlinking a missing relation, and with an integration test after which the existing `FetchCandidateIssues` reports the new blocker.

## 5. Sortie: plan sync and graph API

- [x] 5.1 Add `internal/plan`. It decodes the plan-graph document, gates the version, and checks that every edge's ref resolves. It also computes a preview against the tracker by plan key: creates, updates, parents, relations added and removed, and orphans, along with the tracker-state digest. Verify with tests against a fake adapter for each preview scenario in the plan-sync spec, including a second run with no writes and a removed deliverable reported as orphaned.
- [x] 5.2 Implement apply. It runs in dependency order, refuses before its first write when a capability is missing, refuses a stale preview, stops at the first failure and reports progress, and holds a mutex so only one apply runs at a time. Verify with tests for each of those, and for resuming after a partial failure without duplicates.
- [x] 5.3 Add the CLI command `sortie plan sync --graph <file> [--dry-run]`. Verify with a CLI test against the file tracker fake, and a live dry run against Huly.
- [x] 5.4 Add `POST /api/v1/plan/sync`, `GET /api/v1/plan/graph` (with runtime state joined in and `include_unkeyed`), and `GET /api/v1/plan/capabilities`, behind the control-API authentication from change `sortie-session-control`. Verify with handler tests for each scenario in the plan-graph-api and plan-sync specs, including an error with no partial graph when the tracker is down.
- [x] 5.5 Add `create_issue`, `update_issue`, `set_parent`, and `link_dependency` to the `tracker_api` tool. Advertise and accept each only when its capability is declared, and keep the project scope check. Verify with tool tests for each scenario in the tracker-api-planning-operations spec.
- [x] 5.6 Update the docs: the workflow reference (the `plan` subcommand and the Huly config keys), the HTTP API reference, the Huly adapter notes (the kind mapping and the plan-key attribute), and `CHANGELOG.md`. Verify with `make lint-docs`.

## 6. Workbench backend (FastAPI)

- [x] 6.1 Scaffold the FastAPI app. Add configuration (the store path, the Sortie URL and token, the broker command, and the operator password hash) and sign-in with a signed `HttpOnly` cookie. Verify with tests: unauthenticated requests get `401`, sign-in works, and no response body or header carries the Sortie or broker token.
- [x] 6.2 Watch `openspec/` with `watchfiles`, debounce for 300 ms, run `planlib`, and keep the last valid graph plus the current errors. Verify with a test that edits a fixture store: a valid edit updates the graph within two seconds, and an edit that adds a cycle keeps the last graph and reports the cycle.
- [x] 6.3 Merge the validated graph with Sortie's `/api/v1/plan/graph` by plan key into draft, synced, and orphaned nodes. Poll runtime state every five seconds. Serve `GET /api/graph` and an SSE stream `/api/events`. Verify with tests against a fake Sortie for the draft-beside-synced scenario and orphan marking.
- [x] 6.4 Add the sync proxy: preview through Sortie, then apply with the preview id. Add the Approve action, which calls `planlib.approve` for one change. Verify with tests: nothing reaches Sortie's apply without a confirmation, a missing capability blocks apply, and approving then editing returns the change to draft.
- [x] 6.5 Manage planning sessions. Start one standalone `acp-broker` per session, with the working directory set to the store and the planning prompt file. Find it through the registry. Relay its SSE stream and `POST` commands under the operator cookie. Stop the broker when the session ends. Verify with a test using a fake ACP agent: a message round trip, a permission request and its answer, and reattach with replay after a reconnect.

## 7. Workbench frontend (Vite, Svelte 5)

- [x] 7.1 Scaffold Vite with Svelte 5 and TypeScript. Port the prototype's `DESIGN.md` tokens to CSS variables. Build the 60/40 two-pane shell, which stacks below 1200px. Verify with a component test of the pane widths at 1440px and the stacked order at 900px.
- [x] 7.2 Port the prototype's layout to a framework-free TypeScript module: columns from the backend's depth, row placement, edges, the frontier, and stubs for links to other epics. Verify with unit tests for the chain-of-three case and the drill-down placement of cross-epic stubs.
- [x] 7.3 Build the graph pane:
  - epic and story levels, with drill-down and back;
  - status borders and the unplanned hatch;
  - draft and orphan markers;
  - runtime badges;
  - live updates over SSE that keep the level, the selection, and the scroll position.

  Verify with component tests for each scenario in the node-encoding and live-redraw requirements.
- [ ] 7.4 Build the chat pane: the streaming conversation, tool calls, and permission controls. Add the context card on top, which shows the selected node's details (or ready, active, and unplanned lists when nothing is selected) and attaches the selection to the next message, with a way to remove it. Verify with component tests for the attach and detach scenario, and a permission answer reaching the relay.
- [ ] 7.5 Build the validation panel, where selecting an error selects its node. Build the sync dialog, which shows the preview counts and requires a confirm, and the per-change Approve action. Verify with component tests for a missing capability and for confirm-then-apply.
- [ ] 7.6 Run the impeccable finish review on the built workbench at 1440px and 390px, and fix the material findings. Verify with the reviewer's `ship` disposition.

## 8. End to end

- [ ] 8.1 Write the planning session prompt (store, schema, write limit, run `planlib validate` after every write) and the operator guide for running Sortie, the broker, and the workbench together on one host. Verify by following the guide on a clean checkout.
- [ ] 8.2 Live check against the local Huly. In the workbench chat:
  1. the agent drafts a breakdown for one change;
  2. a planted cycle is reported and fixed in the session;
  3. the person approves the breakdown;
  4. a sync preview is confirmed;
  5. the epic, stories, and dependencies appear in Huly;
  6. Sortie dispatches only the unblocked story;
  7. its running badge appears on the graph.

  Verify by recording the steps and results in the Huly adapter notes.

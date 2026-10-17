## Context

See proposal.md for the motivation and the specs for the requirements. Change `sortie-plan-control` (archived) gave Sortie plan graph version 2, releases, pull-back, cancel, the review gate, and approver fields, and change `workbench-identity` gave the workbench signed-in people with roles. Today in `~/dev/plan-workbench`:

- `planlib.approval` stamps one digest over all deliverables into `breakdown.yaml` (`approve`), and `build_graph` copies the epic's approval onto every story.
- `planlib.validate(root)` takes no outside input. The workbench's `PlanState` re-validates on every file change, and `merge.merge` joins the plan graph with Sortie's.
- `POST /api/projects/{slug}/approve {change}` calls `planlib.approve`. Sync posts the planlib graph to Sortie unchanged.
- `workbench.db` holds only `projects`. Its migrations are numbered SQL files under `src/workbench/sql/`.

## Goals / Non-Goals

**Goals:**

- Approval, release, and the frozen set are computed in one place: an overlay that the workbench applies to the planlib graph, from its own records and Sortie's view.
- planlib stays usable by the planning agent, with no approvals: every story reads as draft, and every check still runs.

**Non-Goals:**

- Removing `status` and `approved_digest` from the schema. They stay accepted and are ignored, so no existing store breaks.
- Editing the graph by hand in the UI. Supersede and amend are written by the planning agent. The UI only confirms them.

## Decisions

### D1. Approvals in `workbench.db`

Migration `002_approvals.sql` adds two tables:

- `approvals(project_id, plan_key, digest, approver_id, approver_name, approved_at)`, keyed by `(project_id, plan_key)`;
- `rereviews(project_id, plan_key, reason, ref, created_at)`, keyed the same way.

Approving a story upserts its row and deletes its re-review. Approving an epic (batch 0) writes a row for every story the epic has. A cancel deletes the approvals of the cancelled story's direct dependents and inserts their re-review rows. Rows are removed with the project.

- *Alternative:* a file in the store that only the backend writes. Rejected: the agent works in the same directory with the same user, so a file is only a convention, and git history would show the agent's commits mixed with approvals.

### D2. The story digest, and planlib's inputs

`planlib.approval.story_digest(deliverable)` is the sha256 of the canonical JSON of the whole deliverable (`review` and `supersedes` included). `validate(root, approvals=None, frozen=None)`:

- `approvals` maps plan keys to digests. A story is `approved` when its digest matches. An epic is `approved` when any of its stories is, `draft` when it has a breakdown, and `unplanned` otherwise.
- `frozen` maps plan keys to their approved digests. A frozen story that is gone, or whose digest differs, is a `frozen` error.
- Each story node gains `review` (default `human`), and `digest` (exposed to the workbench, not sent to Sortie).
- `supersedes` rewires edges: every block edge whose blocker is the superseded story points at the replacement instead.

`approve` (the file writer) is removed, and the CLI loses nothing: it never called it.

### D3. The overlay

`workbench.plan_overlay.overlay(graph, approvals, rereviews, tracker)` runs in `Hub.rebuild` and on every sync. It adds to each story:

- `plan_status`: `draft`, `held`, `ready`, `released`, `frozen`, or `needs_rereview`;
- `held_by`: the unapproved direct blockers;
- `rereview`: the reason and the ref;
- `approved_by` and `approved_at`.

The sync graph is built from the same overlay: `release: true` for `ready` and `released` stories, and `review`, `approved_by` (`{name, id}`), and `approved_at` for approved ones. `digest` and the overlay-only fields are stripped before the graph goes to Sortie.

Frozen means Sortie reports runtime, a satisfaction, or a tracker state other than the plan's backlog and release states. Sortie's plan graph gains `plan_states` (`{release, backlog, cancel, done}`), a one-field addition, so the workbench never guesses state names. `PlanState.refresh` passes the frozen set to `validate`. The validator then refuses edits to started stories.

### D4. Edits to released stories

After every refresh, the hub compares each `released` story's current digest with its approval. A mismatch on a story that is not frozen makes the backend call Sortie's pull-back. The approval stays, but no longer matches, so the story reads as draft. When Sortie answers `already_claimed`, the story is frozen on the next poll, and the validator then reports the edit.

### D5. Routes

All of these need the `approver` role:

| Route | Action |
|---|---|
| `POST /api/projects/{slug}/approve` | `{"keys": [...]}` approves stories; `{"epic": "<change>"}` is batch 0 |
| `POST /api/projects/{slug}/stories/pull-back` | `{"key": ...}`, through Sortie |
| `POST /api/projects/{slug}/stories/cancel` | `{"key": ...}`, through Sortie, then the dependents' re-reviews |
| `POST /api/projects/{slug}/stories/supersede` | `{"key": <replacement>}`: checks that the replacement declares `supersedes`, then cancels the replaced story through Sortie, without re-reviews |

Each answers with the refreshed graph's node, and logs the actor.

### D6. Import of old approvals

On project open, for each breakdown with `status: approved` whose `approved_digest` still matches the old all-deliverables digest, and with no approval rows for its stories, the workbench writes batch 0 with approver `migration|<change>`, named "Imported approval".

## Risks / Trade-offs

- [The agent edits a released story in the window before the pull-back] → Sortie may dispatch the old content. The pull-back runs within one refresh of the edit, and an edit that loses the race becomes a frozen-story error, so it is never silent.
- [The frozen check depends on Sortie being reachable] → With Sortie down, nothing is frozen, so edits are accepted. Sync needs Sortie anyway, and the next poll freezes the story again before any sync can write.
- [Batch 0 approves stories the approver has not opened one by one] → That is the intent of batch 0. The epic view lists them before the approval.

## Migration Plan

Deploy the workbench. Opening each project imports its old approvals. Sortie must be on `plan-bench` with plan control, for releases and the `plan_states` field. Without plan control the overlay still works, and Sortie releases nothing.

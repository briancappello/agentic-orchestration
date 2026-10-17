## Why

The loop we want is: plan an epic, approve it, send it to agents, then keep adding stories to it as the work teaches us more. The tracker gives non-technical people visibility. Engineers do all the work in the workbench, and nobody has to touch the tracker.

The approval in change `plan-to-tracker-dag` cannot support that loop:

- **It covers the whole epic.** One digest covers every deliverable in `breakdown.yaml`. Adding one story returns the whole epic to draft, and sync skips draft changes, so no update reaches the tracker until someone approves the whole epic again.
- **The agent can approve its own work.** Approval lives in `breakdown.yaml`, a file the planning agent writes. The digest detects edits, but it cannot prove that a person approved. That is acceptable only while approval does not start any work, and this change makes approval start work.
- **Approval does not release work.** Synced stories stay in `Backlog`, so a person must move each one to `Todo` in the tracker.
- **A story can start too early.** Sync links only issues that have a plan key. A story that depends on a story in an epic that was never synced gets no blocker in the tracker.
- **Nothing tells you what to do when plans change.** There is no rule for editing a story that agents are working on, and no rule for cancelling a story that other stories depend on.

## What Changes

- **Approval moves out of the spec store.** The workbench keeps approvals in its own database (`workbench.db`). Each approval records the story's plan key, the digest of that story's content, the approver's identity (change `workbench-identity`), and the time. The planning agent cannot write it. **BREAKING:** `status` and `approved_digest` leave `breakdown.yaml`. The planning schema drops them, and `planlib approve` is removed.
- **Approval is per story, with a first batch.** An epic's first approval covers every story the epic has at that moment (batch 0). After that, people approve new stories one at a time or in groups, and the stories approved earlier stay approved. Each approval covers the digest of one story. When a story's content changes, only that story returns to draft.
- **Approval and release are two statuses.**
  - Approval: `draft` or `approved`.
  - Release, for an approved story:
    - `held` when at least one direct blocker is not approved yet;
    - `ready` when every direct blocker is approved.
  - A `ready` story is released: the next sync asks Sortie to move it to `Todo` (change `sortie-plan-control`). Release is one-way, and only a pull-back undoes it. Sortie's blocker check then orders the work, so the gate only needs to look at direct blockers.
- **A story is frozen once it starts.**
  - A story can be edited only before it starts: while it is held, or while it is in `Todo` and not running. A story in `Todo` is first pulled back by Sortie's atomic pull-back, so the edit cannot race with dispatch.
  - Once an agent starts a story, its content is frozen. The workbench passes planlib the set of frozen stories, and planlib rejects any change to a frozen story's content and any attempt to remove it.
  - After a story starts, scope changes only through new stories.
- **Amend, supersede, and cancel.** These are the only operations on a story that has started.
  - *Amend* adds a new story that depends on the original.
  - *Supersede* adds a replacement and records `supersedes: <key>` in `breakdown.yaml`. The replacement takes over the original's dependents automatically, and Sortie cancels the original.
  - *Cancel* stops the story with no replacement. Its direct dependents move to `needs_rereview` with the reason `blocker_canceled` and the key of the cancelled story. Their approval is withdrawn until a person approves them again. Stories further down only stay held.
  - All three need the `approver` role.
- **A claim that the work was already done.** An agent may report that a story's outcome already held. That claim must cite where the work was done: a plan story, or a merged commit on the base branch. A claim that cites a plan story becomes a supersede by that story. A claim that cites nothing satisfies nothing: the story moves to `needs_rereview` with the reason `unverified_no_change`.
- **Each story has a review gate.** `breakdown.yaml` gains a `review: human | criteria` field for each deliverable. The planning agent proposes it, and the person who approves the story accepts it. Change `sortie-plan-control` enforces the gate.
- **External blockers.** A tracker blocker without a plan key, such as a relation someone added by hand or work that is not code, appears on the graph as an external node. The workbench shows it as satisfied only when its tracker state is `Done`.
- **The workbench UI.** The graph shows each story's approval and release status, the reason a story is held or needs re-review, and frozen stories. The epic view lets you approve the first batch, select several draft stories and approve them, pull a story back, cancel it, and supersede it. Sync sends each story's approval and approver to Sortie, and Sortie writes them to the tracker.

## Capabilities

### New Capabilities
- `planning/story-approval`: per-story approval and the first batch, the approval record and where it is kept, the digest of each story, the return to draft, and the role that may approve.
- `planning/release-gate`: the `held` and `ready` statuses, the rule that only direct blockers count, one-way release, and the pull-back that comes before an edit.
- `planning/story-lifecycle`: the freeze once a story starts, amend, supersede (with dependents taken over), cancel (with dependents sent to `needs_rereview`), the claim that work was already done and its evidence, and the `needs_rereview` reasons.
- `planning/review-gate`: the `review` field of each deliverable and who sets it. Change `sortie-plan-control` enforces it.

### Modified Capabilities

None. This store has no archived specs yet. This change revises the approval requirements of change `plan-to-tracker-dag` (`planning/breakdown-artifact`, `planning/plan-validator`, `planning/plan-workbench`): approval moves out of the breakdown file, and the validator gains the frozen-story check and `supersedes`.

## Impact

- Project spec stores: the planning schema (`openspec/schemas/planning/`, copied into each project's store from the workbench's `src/workbench/store_template/`) drops `status` and `approved_digest`, and adds `review` and `supersedes` to each deliverable. Every existing `breakdown.yaml` needs a one-time migration. An epic that is approved today becomes batch 0.
- planlib (`src/planlib/`): `approval.py` becomes a digest for each story, with no file writes. `graph.py` emits `approval`, `release`, and the held and re-review reasons for each story. Validation accepts a frozen set and checks `supersedes`.
- Workbench (`src/workbench/`): approval and release records in `workbench.db`; the approve, pull-back, cancel, and supersede routes; sync sends release, approval, and approver for each story; the graph and epic views show these statuses.
- Depends on change `workbench-identity`, for the approver, and on change `sortie-plan-control`, for release, pull-back, cancel, the approver fields, and the review gate.
- Out of scope:
  - dispatch across several projects; Sortie still runs agents for one project only;
  - plan writes to trackers other than Huly;
  - ordering between epics; the edges between stories are the only edges that gate work.

## Context

The workbench already holds each project's validated graph (`hub.py`, live
over server-sent events) and calls Sortie's `POST /api/v1/plan/sync` in two
steps, preview then apply (`sync.py`). Sortie's sync is idempotent by plan
key and skips drafts.

## Decisions

### D1. The backend runs the sync loop, not the browser

The loop must run with no browser open: an approval made through the API,
or a change the planning agent writes to the store, still reaches the
tracker. Each project runtime gets one sync task, woken by an event. A wake
during a run sets a flag that causes exactly one more run. A short debounce
(about 300 ms) folds a burst of approvals into one sync.

### D2. Preview, then apply, in one step

The task calls preview, then applies that same preview id, so Sortie's
stale-preview check still protects against a tracker that changed in
between. A `stale_preview` answer starts one immediate retry. A missing
capability stops the task until the next trigger, and the status says which
capability is missing.

### D3. What triggers a sync

Approvals, pull-backs, cancels and supersedes trigger one directly, in their
routes. A store change triggers one when the validated graph's digest of
approved stories changes; a draft edit alone does not.

### D4. Refresh after a release

Sortie's `POST /api/v1/refresh` runs one poll at once. The workbench calls it
only when the apply result released at least one story.

## Risks / Trade-offs

- **No last look.** The preview showed relation removals and orphans before
  they happened. Neither destroys anything, the status shows them after each
  sync, and the planning agent's edits are visible in the graph as it works.
- **The planning agent can unblock work by editing the plan.** It still
  cannot approve: an edit to an approved story returns it to draft and pulls
  it back. Removing a dependency between two approved, unstarted stories
  can release the later one sooner, as a manual sync would.

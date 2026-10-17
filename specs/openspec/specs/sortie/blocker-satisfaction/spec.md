# sortie/blocker-satisfaction Specification

## Purpose
Decides when a blocker lets the stories it blocks start. A story starts only after the work it depends on is merged, not just when someone sets its blocker's tracker state.

## Requirements

### Requirement: Satisfied from Sortie's own record
With plan control on, Sortie SHALL decide each blocker of a candidate story as follows:
- A blocker **with a plan key** SHALL be satisfied only when Sortie's own records show one of these:
  - Sortie latched a merge commit for the blocker's pull request;
  - the blocker has a confirmed no-change claim (`sortie/no-change-evidence`).
- A blocker **without a plan key** SHALL be satisfied only when its tracker state is `tracker.done_state`.
- A blocker in `tracker.cancel_state` SHALL NOT be satisfied, whatever Sortie's records show.
- A blocker whose state Sortie cannot read SHALL NOT be satisfied.
- When the adapter cannot report plan keys, every blocker SHALL follow the rule for blockers without a plan key.

A tracker state alone SHALL NOT satisfy a blocker with a plan key. A merged pull request SHALL count as reviewed, even when the forge required no review. Sortie SHALL dispatch a candidate only when every blocker is satisfied. The retry path and the dry run SHALL use the same rules. With plan control off, Sortie SHALL keep the old rule: any blocker in a terminal state is satisfied.

#### Scenario: A blocker merged
- **WHEN** story `billing/b1` is blocked by `billing/a3`
- **AND** Sortie latched the merge commit of the pull request for `billing/a3`
- **THEN** `billing/b1` can be dispatched

#### Scenario: A blocker a person moved to Done
- **WHEN** a person moved `billing/a3` to `Done` in the tracker
- **AND** Sortie has latched no merge commit for it and holds no confirmed no-change claim
- **THEN** `billing/b1` is not dispatched

#### Scenario: A cancelled blocker
- **WHEN** `billing/a3` is in `Canceled`
- **THEN** `billing/b1` is not dispatched

#### Scenario: A blocker that is not planned
- **WHEN** `billing/b1` is blocked by `HULY-88`, "Legal approves invoice wording", which has no plan key
- **AND** a person moves `HULY-88` to `Done`
- **THEN** `HULY-88` no longer blocks `billing/b1`

#### Scenario: A blocker that is not planned is cancelled
- **WHEN** `HULY-88` has no plan key and a person moves it to `Canceled`
- **THEN** `billing/b1` is not dispatched

#### Scenario: Plan control off
- **WHEN** `tracker.release_state` is not set
- **AND** a blocker is in any terminal state
- **THEN** the blocker is satisfied, as before this change

### Requirement: Merge records survive restarts
The record that a story's pull request merged SHALL be durable. It SHALL survive a restart of Sortie and the removal of the story's workspace. A later merge of the same story SHALL NOT erase the fact that it merged.

#### Scenario: Restart after a merge
- **WHEN** Sortie latched the merge commit for `billing/a3`
- **AND** Sortie restarts and the workspace of `billing/a3` is gone
- **THEN** `billing/a3` still satisfies `billing/b1`

### Requirement: Say why a story waits
Sortie SHALL report, for each blocker that is not satisfied, the reason: `not_merged`, `awaiting_merge_record`, `canceled`, `not_done`, `unverified_no_change`, or `unknown`. `awaiting_merge_record` SHALL mean that the blocker's tracker state is terminal but Sortie holds no merge record for it. The plan graph (`sortie/plan-graph-api`) and the dispatch logs SHALL carry these reasons.

#### Scenario: A card dragged past its merge
- **WHEN** a person moved `billing/a3` from the handoff state to `Done` before its pull request merged
- **THEN** the plan graph reports `billing/b1` as blocked by `billing/a3` with `awaiting_merge_record`

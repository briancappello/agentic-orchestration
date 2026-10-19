# sortie/no-change-evidence Specification

## Purpose
Lets an agent claim that a story's outcome already held, and lets that claim satisfy the stories it blocks only when it cites work that Sortie can confirm.

## Requirements

### Requirement: A claim cites its evidence
With plan control on, an agent that writes `no-change-needed` to `.sortie/status` SHALL also write `.sortie/evidence.json`. The file SHALL cite exactly one of these:
- `{"kind": "commit", "sha": "<full commit id>"}`: a commit that already does the work;
- `{"kind": "plan_key", "plan_key": "<key>"}`: the plan story that already does the work.

The file MAY add a `note` of at most 2,000 characters; Sortie SHALL refuse a longer note as unparsed. Sortie SHALL treat the file as untrusted input from the agent. A missing file, a file that does not parse, or a file that cites nothing SHALL make the claim unverified.

#### Scenario: A claim without evidence
- **WHEN** the agent of `billing/retry` writes `no-change-needed` and no evidence file
- **THEN** Sortie records the claim as unverified

### Requirement: Sortie confirms a citation
Sortie SHALL confirm a citation itself, on the host, and never in the agent's workspace:
- A cited commit SHALL be confirmed only when it is reachable from the base branch in Sortie's host-owned mirror (`sortie/guest-repository-sync`). Without a mirror, a cited commit SHALL stay unverified.
- A cited plan key SHALL be confirmed only when it names another plan story in the same project. The claim SHALL then satisfy the stories it blocks only while the cited story is satisfied.

Sortie SHALL record a confirmed claim durably, with its citation, so that a restart keeps it. Sortie SHALL record an unverified claim with its reason.

#### Scenario: A commit on the base branch
- **WHEN** the agent of `billing/retry` cites commit `4f1c…` and that commit is on `main` in the mirror
- **THEN** the claim is confirmed
- **AND** `billing/retry` satisfies the stories it blocks

#### Scenario: A commit that is not merged
- **WHEN** the cited commit is only on another branch
- **THEN** the claim is unverified with the reason `commit_not_on_base`

#### Scenario: A plan story that did the work
- **WHEN** the agent of `billing/retry` cites plan key `payments/http-client`
- **AND** `payments/http-client` has not merged yet
- **THEN** `billing/retry` does not satisfy its dependents yet
- **AND** it does so once `payments/http-client` merges

### Requirement: Report the claim to the plan
The plan graph (`sortie/plan-graph-api`) SHALL report each story's claim: `no_change_confirmed` with its citation, or `unverified_no_change` with its reason. A claim that cites a plan key SHALL also be reported as a proposed supersede of the claiming story by the cited one, so a plan client can record it.

#### Scenario: A proposed supersede
- **WHEN** the agent of `billing/retry` cites plan key `payments/http-client`
- **THEN** the graph node of `billing/retry` carries a proposed supersede by `payments/http-client`

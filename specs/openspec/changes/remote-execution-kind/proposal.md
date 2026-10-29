## Why

The Ortus Nova spec store's `agent-platform-workers` adds a `remote`
execution environment kind: Sortie hands each run to a worker host that dials
in (`agent-platform/worker-dispatch`, built by `matcher-and-worker-api` and
`matcher-wiring` in ortusnova/sortie). This spec still accepts only `local`
and `smolvm` (that change's design D16).

## What Changes

- `environment.kind` accepts `remote`. "smolvm excludes SSH workers" is
  unaffected, because `remote` is a kind of its own.

## Capabilities

### Modified Capabilities

- `sortie/execution-environment`: "Workflow selects an execution environment kind" accepts `remote`.

## Impact

- Spec only here. The code is in ortusnova/sortie (`matcher-wiring`).

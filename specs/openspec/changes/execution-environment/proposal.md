## Why

We want agents to use tools freely: build, test, install packages, run Docker. Today Sortie runs everything as the operator on the host, in a workspace the agent can write to. The agent launch is abstracted (local or SSH), but nothing else is:

- Hooks run on the host.
- Self-review verification commands run on the host.
- Reaction triage runs on the host.
- Sortie's own `git` reads (handoff evidence, the self-review diff) run on the host, against a `.git` the agent controls. A planted fsmonitor or filter runs there too.

The smolvm spike (sortie branch `spike/smolvm`) showed that a microVM per issue works on our host. Inside the VM, a real opencode ACP session fixed a bug and committed. It never saw its API key. It boots in about a second from a prebuilt stack pack.

## What Changes

- Sortie gains an execution environment for each workflow. The environment decides where workspace code runs.
  - Kind `local` is today's behavior and stays the default.
  - Kind `smolvm` runs each issue in its own microVM.
- Everything that executes code from the workspace goes through the environment:
  - the agent launch, including the credential check
  - all four hooks
  - self-review verification commands
  - reaction triage
  - Sortie's own git inspection
- With `smolvm`:
  - The workspace lives on the VM's own disk. Sortie never runs `git` or any workspace code on the host.
  - Only the per-issue `.sortie` control directory is shared with the host. Sortie already treats that directory as agent-authored, untrusted input.
  - Egress is deny-by-default with a per-workflow host allowlist.
  - API keys reach the agent only through smolvm credential bindings. The guest sees a placeholder, never the value.
  - Sortie refuses to dispatch when an agent kind's credential variable would otherwise reach the guest in plain text.
- With `smolvm` and a configured `environment.smolvm.repository`, git crosses the boundary only as bundles, and the guest holds no git credentials and needs no egress to the git host:
  - **In.** Sortie keeps a bare mirror of the repository that only the host owns. It seeds a new workspace from a bundle of the base branch, and before every later run it sends a fresh bundle of the base and the issue branch into the guest as `origin/*`.
  - **Out.** At the end of each run, the guest bundles the issue branch. Sortie imports exactly that one ref into the mirror, with hooks and fsmonitor disabled and object checks on, then pushes it upstream with its own credentials. A branch someone else moved is never overwritten.
  - **Pull requests.** Sortie opens, or finds, the issue's pull request through its SCM adapter. GitHub, GitLab, and Gitea adapters gain an optional pull-request opener.
  - **Trusted metadata.** Sortie records the branch, commit, and pull request itself. PR reactions read that record, not the agent-writable `.sortie/scm.json`.
  - A failed export fails the run, which is retried. The tracker handoff happens only after a successful export.
- Sortie tools (the MCP tool server) keep running on the host with the tracker credentials. The guest reaches them through a per-issue Unix socket.
- A new optional `environment.host_prefix` keeps part of the agent command on the host, for example the ACP broker. Only the rest runs in the environment.
- A separate tool, `smol-builder`, builds stack packs. Each project declares its stack in its own repository, in `smol-builder.toml`: a base of Linux, the agent and common tools, plus language layers such as `go`, `node`, `python` and `rust`. Each project may add one layer of its own. The tool builds a pinned, reproducible smolvm pack, and a workflow names that pack.
- `smolvm` and `worker.ssh_hosts` are mutually exclusive. When the environment cannot start, dispatch waits. It never falls back to local execution.

## Capabilities

### New Capabilities
- `sortie/execution-environment`: the environment setting, which operations run inside it, the host prefix, the SSH exclusion, and the no-fallback rule.
- `sortie/smolvm-environment`: the VM per issue: its lifecycle, the pack, the guest workspace, the shared control directory, resources, egress, credentials, and how leftover VMs are cleaned up.
- `sortie/guest-tool-server`: how an agent inside the environment reaches Sortie's MCP tools, which run on the host.
- `sortie/guest-repository-sync`: the host-owned mirror, seeding and refreshing the guest repository with bundles, exporting the issue branch, the push rules, and the trusted SCM record.
- `sortie/scm-pull-request-open`: how an SCM adapter opens, or finds, the pull request for a branch.
- `smol-builder/stack-definition`: the `smol-builder.toml` format, the layer library, the layer order, and the project layer.
- `smol-builder/stack-builder`: how `smol-builder` turns a stack definition into a pinned smolvm pack, and what it reports.

### Modified Capabilities

None. This store has no archived specs yet.

## Impact

**Code in the Sortie fork (`~/dev/sortie`)**, on a branch off `feat/session-control`:

- `internal/config`: a new `environment` block.
- A new `internal/environment` adapter family with kinds `local` and `smolvm`, resolved through `internal/registry`.
- `internal/agent/agentcore` (`LaunchTarget`) and every adapter's launch path.
- `internal/workspace`: hooks, lifecycle, and handoff evidence.
- `internal/orchestrator`: worker, self-review, reaction triage, MCP config, startup cleanup, and the export step before the tracker handoff.
- A new `internal/gitsync` package: the host mirror, bundle seeding, import, and push.
- `internal/domain` and `internal/scm/{github,gitlab,gitea}`: an optional `PullRequestOpener` interface and its three implementations.
- `internal/persistence`: run history gains the pack digest and the exported commit.
- `cmd/sortie`: blank imports, and a new `mcp-relay` subcommand.

**New repository** `~/dev/smol-builder`: the `smol-builder` tool (Go, no CGo) and the layer library. It replaces the spike's Python builder.

**Dependencies:**

- smolvm 1.26.1 on the Sortie host, pinned and run as a CLI. Sortie links no smolvm code.
- podman or docker on the machine that builds stacks.

**Documentation in the fork:**

- `docs/workflow-reference.md`
- the architecture sections on configuration, workspaces, the agent adapter contract, and security
- `CHANGELOG.md`
- a smolvm environment guide

**Upstream:** every change is additive. With the default `local` kind, behavior is unchanged.

**Out of scope:**

- Committing work the agent left uncommitted. Only committed work on the issue branch is exported; the rest stays in the guest workspace for the next run.
- Path-based policy on exported commits, such as refusing changes to CI or sandbox configuration.
- Warm branch pools.
- Pulling packs from a registry.
- Agents that authenticate with OAuth files instead of API keys.

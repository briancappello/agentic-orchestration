The Sortie work is in the fork (`~/dev/sortie`), on a branch off `feat/session-control`. Run `make help` to find the lint and test targets; every Sortie task ends with them passing. Tests that need smolvm are gated by `SORTIE_SMOLVM_TEST=1`, and without it they skip cleanly. The stack tool lives in the new repository `~/dev/agent-stacks`. The spike scripts on sortie branch `spike/smolvm`, under `spikes/smolvm/`, are the reference for every smolvm behavior below.

## 1. Remaining smolvm checks

- [ ] 1.1 Extend the spike with three mounts on one machine: a read-write `-v` at `/run/sortie/control`, a read-only `-v` at `/opt/sortie` holding a copy of the Sortie binary, and `--mount-socket` at `/run/sortie/tools.sock`. Check that `/opt/sortie/sortie --version` runs in the guest, that a guest write to `/opt/sortie` fails, and that `ln -s /run/sortie/control /workspace/.sortie` then shares writes both ways. Record the commands and output in the change's `verification.md`.
- [ ] 1.2 In the spike VM, run claude-agent-acp and codex with a credential binding for their API hosts, and record for each whether its HTTPS client accepts the substituted certificate. Verify by recording one successful turn per agent, or the exact TLS error, in `verification.md`. Then list every agent kind as supported or not supported in the environment guide draft.
- [ ] 1.3 Stop a running `opencode acp` turn by sending SIGTERM to the `smolvm machine exec` process. Record what the next `session/load` (resume) of that session sees. Verify by recording the result in `verification.md`. This is the measurement the "no graceful TERM" risk asks for.

## 2. agent-stack tool

- [ ] 2.1 Create `~/dev/agent-stacks` with a Go module, `cmd/agent-stack`, and a `Makefile` with `test` and `lint` targets. Port `base`, `go`, `node`, `python`, and `rust` from the spike's `golden/` with the same pins. Verify with `go build ./...` and `make test` on the empty test set.
- [ ] 2.2 Implement parsing and validation of `agent-stack.toml`: unknown keys, unknown or duplicate layers, project layer paths that escape the repository or are missing, and a project layer whose first instructions are not `ARG BASE` / `FROM ${BASE}`. Verify with table tests for every rejection in the stack-definition spec, each asserting that the error names the entry.
- [ ] 2.3 Implement chain resolution: sorted library layers, then the project layer, each with a content-hash tag. Verify with unit tests: `["node","go"]` and `["go","node"]` yield identical tags, a changed layer file changes only its own tag and the tags after it, and the project layer is always last.
- [ ] 2.4 Implement the build: podman or docker (detected, with the missing program named), reuse of existing tags, `save`, a builder machine with the image's `Env` and `WorkingDir` passed as `-e` and `-w`, `pack create --from-vm`, an atomic rename into the output, deletion of the builder machine on every path, and the JSON report. Verify with an integration test gated by `AGENT_STACK_SMOLVM_TEST=1`. It builds `["go"]`, checks that `go version` resolves through `PATH` in a machine created from the pack, checks that `pack_sha256` matches the file, and checks that a forced failure leaves the previous output intact and no builder machine behind.
- [ ] 2.5 Write the README: the stack file format, the layer library, and an example `project_layer`. Verify that its example commands run as written.

## 3. Environment configuration and the local kind

- [ ] 3.1 Add the `environment` block to `internal/config`: `kind`, `host_prefix`, and every `smolvm` key in design decision 1, with the validations from the execution-environment and smolvm-environment specs. Those are: unknown kind, an empty prefix element, `smolvm` together with `worker.ssh_hosts`, a missing or unreadable pack, and malformed hosts or credentials. Verify with config tests for each error, including the reload case that keeps the previous config.
- [ ] 3.2 Add `internal/environment` with the interface from decision 1 and kind registration through `internal/registry`. Add the `local` kind, which is a plain host `exec.Cmd` with the workspace as cwd and no-ops for everything else. Blank-import the kinds in `cmd/sortie`. Verify with unit tests for `local` and a registry test that resolves both kinds.
- [ ] 3.3 Route hooks (`RunHook`, `Prepare`, `Finish`, `Cleanup`, `CleanupByPath`), self-review verification commands, reaction triage, the self-review diff, and handoff evidence through `Environment.Command`. Under `local` they keep their current host behavior, and the triage files keep their host temporary directory. Verify that every existing test in `internal/workspace` and `internal/orchestrator` passes unchanged, and add one test per call site that asserts it calls the environment.
- [ ] 3.4 Change the handoff-evidence fingerprint to hash untracked files through `git hash-object --stdin-paths`, run in the environment, instead of reading the files on the host. Verify that the existing handoff-evidence tests pass, and add a test where an untracked file changes and the fingerprint changes.
- [ ] 3.5 Record the environment kind and VM name in `.sortie/environment` at preparation. Recreate a workspace whose recorded kind differs from the configured kind. A workspace with no record counts as `local`. Verify with lifecycle tests: an unrecorded workspace under `local` is kept, and the same workspace under a fake second kind is removed and prepared again, with `after_create` run.

## 4. Launch carrier

- [ ] 4.1 Add `LaunchTarget.RemoteLaunch`, `Remote`, `MCPInGuest`, and `GuestPath`. Move the five `sshutil.BuildSSHLaunch` call sites onto `RemoteLaunch`: opencode, codex, clientprotocol, forkperturn, and `AuxiliaryCommand`. Verify that every SSH test in `internal/agent/...` passes unchanged, and that `GuestPath` is the identity for local and SSH targets.
- [ ] 4.2 Switch the MCP conditions in opencode, clientprotocol, and codex to `Remote && !MCPInGuest`. Make claude-code and copilot pass `GuestPath(mcpConfigPath)`. Verify with one table test per adapter over three targets (local, SSH, and an environment target), asserting whether MCP servers are passed and which path is used.
- [ ] 4.3 Apply `host_prefix` to the session launch and the credential check only. Verify with tests: the prefix precedes the carrier for both launches, it is absent from hook and auxiliary commands, and under `local` the result equals today's prefixed `agent.command`.

## 5. smolvm kind

- [ ] 5.1 Write the smolvm CLI client: the version check against `1.26.x`, `machine ls --json`, create, start, stop, delete, exec, and the error type carrying the exit code and an 8 KiB stderr tail. Fake the CLI with a scripted binary in unit tests. Verify with unit tests for the version refusal (startup and reload), parsing of the spike's recorded `ls --json` output, and error wrapping.
- [ ] 5.2 Implement `Prepare`: create `.sortie` on the host, derive the VM name and labels, create the VM from the pack with resources, the allowlist, credentials, and exactly the three mounts, then start it. Report "created now" only after a create. Verify with fake-CLI tests asserting the exact argv, including that `--nested`, `--allow-system-mounts`, `--docker-socket`, `-p`, and any other `-v` never appear. Add a gated test that prepares a real VM from the spike's base pack.
- [ ] 5.3 Implement `Command` with `smolvm machine exec --name -i -w`, using `-e` for session identity and `SORTIE_ENVIRONMENT`, `--secret-env` for `pass_env`, and never the session token or API URL. Classify CLI failures before the guest command starts as connection failures. Verify with fake-CLI argv tests, and a gated test where a hook's `uname -n` output lands in the guest and not on the host.
- [ ] 5.4 Link `/workspace/.sortie` after `after_create`, and fail preparation, without modifying anything, when the entry already exists. Verify with a gated test: the agent's `status` write is read on the host, a planted symlink is refused, and a cloned repository holding `.sortie` fails preparation with the path in the error.
- [ ] 5.5 Implement `Release` (stop), `Remove` (`before_remove` in the guest, delete, then remove the host directory) and `Sweep` (managed label, missing workspace, and no running worker). Wire them to worker exit, every workspace cleanup path, startup, and the periodic sweep. Verify with orchestrator tests using a fake environment, plus a gated test that a deleted workspace's VM is swept and an unlabeled VM is left alone.
- [ ] 5.6 Add the credential preflight: an agent kind's declared credential variable that is set on the host but listed in neither `credentials` nor `pass_env` fails dispatch with its name. Verify with preflight tests for a bound variable, a `pass_env` variable, an unset variable, and the failing case.
- [ ] 5.7 Record the pack SHA-256 in VM labels and in the run history (a new column, with a migration). Show the kind and VM name in `/api/v1/state` and the per-issue detail. Verify with persistence migration tests and server tests.

## 6. Guest tool server

- [ ] 6.1 Add the `sortie mcp-relay <socket>` subcommand: it copies stdio to the socket, and when the connection closes before any response it exits non-zero with `tool server unavailable`. Verify with tests against a listening socket, a socket that closes immediately, and a missing socket.
- [ ] 6.2 Add the per-issue host listener under the state directory. It starts `sortie mcp-server` with the issue's session environment for each connection, is recreated at startup for every workspace with a VM, and is removed with the workspace. Verify with tests: two issues each get their own identity, and a listener restarted at the same path serves a new connection.
- [ ] 6.3 Generate the guest `mcp.json` for smolvm sessions, naming `/opt/sortie/sortie mcp-relay /run/sortie/tools.sock`, and keep the current output for `local` and SSH. Maintain the read-only binary directory with a copy of the running binary. Verify with `GenerateMCPConfig` tests for each kind, and a gated test where an agent in a VM calls `sortie_status` and gets its own issue's status.

## 7. Documentation

- [ ] 7.1 Document `environment` in `docs/workflow-reference.md` and in the fork's configuration, workspace, agent adapter contract, and security architecture sections. Add a `CHANGELOG.md` entry. Verify that every key and validation error in the specs appears in the reference.
- [ ] 7.2 Write the smolvm environment guide in the fork. It covers installation and the pinned version, building a pack with `agent-stack`, `allow_hosts` for each agent, credential bindings including git over HTTPS with `set_header`, cloning in `after_create`, the agent support list from 1.2, `smolvm machine egress-events`, `smolvm pack prune`, and rollback. Verify that its example workflow passes `sortie validate`.

## 8. End-to-end check

- [ ] 8.1 Build a pack with `agent-stack` for a small Go repository. Run Sortie with the file tracker, the `agent-client-protocol` kind running `opencode acp`, `host_prefix` set to the ACP broker, and `environment.kind: smolvm`. Confirm all of the following and record the commands and output in `verification.md`:
  - `after_create` clones inside the VM;
  - the agent fixes a failing test, commits, and pushes to a scratch GitHub repository through a `set_header` credential binding;
  - `sortie_status` works from the VM;
  - handoff evidence sees the commit;
  - the API key and the session token are absent from the guest;
  - the VM stops after the run and is deleted when the issue reaches `Done`.

## Context

See proposal.md for the motivation. The facts below come from the Sortie fork (`feat/session-control`) and from the smolvm spike on branch `spike/smolvm`, under `spikes/smolvm/`.

**How Sortie runs workspace code today**

- **Agent launch.** `agentcore.ResolveLaunchTarget` returns either a local binary or an SSH carrier: `ssh host 'cd ws && <import env from stdin> && agent'`. Adapters branch on `target.RemoteCommand != ""` in about a dozen places. In a remote launch they skip the local canary and drop the MCP config. `opencode` and `clientprotocol`, for example, pass no MCP servers remotely.
- **Hooks.** `workspace.RunHook` runs `sh -c` on the host, with the host workspace as its cwd. In SSH mode the hooks still run on the host, and receive `SORTIE_SSH_HOST`.
- **Self-review.** Verification commands run `sh -c` on the host (`self_review.go`). The review diff runs host `git add -N` and `git diff`.
- **Handoff evidence.** `CaptureHandoffEvidenceBaseline` and `CompareHandoffEvidenceBaseline` run host `git status`, `diff`, and `ls-files`, and read untracked files on the host. `core.fsmonitor=false` is set on Windows only.
- **Reaction triage.** The triage command runs as a hook on the host, with input and result files in a host temporary directory.
- **Control files.** The `.sortie` directory carries `status`, `scm.json`, `review_verdict.json`, notification slots, `state.json`, dispatch identity, `review_summary.md`, and `mcp.json`. Every read goes through `workspacekit`. It opens through `os.Root`, refuses links and non-plain files, and caps sizes, because this directory is agent-authored.
- **MCP tools.** `GenerateMCPConfig` writes `.sortie/mcp.json`. That file names the absolute host path of the Sortie binary, `mcp-server --workflow <path>`, and an env block. The agent spawns the tool server itself. The tool server reads the workflow and holds tracker credentials.
- **Broker.** The ACP broker is used as a prefix of `agent.command` (change `acp-broker`).

**What the spike established on this host** (smolvm 1.26.1)

- `smolvm machine exec --name N -i -w DIR -e K=V -- argv` is a byte-exact pipe. It needs no daemon. It propagates EOF, stderr, and the exit code.
- SIGTERM or SIGKILL to the CLI, or `--timeout`, kills the guest command and its process group. Nothing is delivered gracefully. Daemonized processes survive until the VM stops.
- The HTTP API's WebSocket exec stalls on 64 KiB frames, so it is not used.
- Egress allowlists hold. Changes to them apply live, and denials are logged (`egress-events`).
- Credential bindings work with opencode (Bun). A placeholder in a query string is refused.
- A host directory mounted with `-v` at `/workspace/.sortie` sits inside the guest-disk workspace, and both sides see each other's writes. Guest-written files appear owned by the host user, and the guest can plant symlinks.
- `--mount-socket HOST:GUEST` reaches a host Unix-socket listener. When nothing is listening, a guest connect succeeds and then reads EOF. A listener restarted at the same host path works without restarting the VM.
- A virtiofs mount is about 8x slower than the guest disk for small files.
- Stack packs (`create --from x.smolmachine`) take about 0.2 s to create once the pack is extracted, and about 0.7 s to start. A pack built with `pack --from-vm` drops the image's `ENV` and `WORKDIR`, but keeps the builder's `-e` and `-w`.

**Constraints**

- No CGo, so Sortie drives smolvm only through its CLI.
- Changes stay additive, so the fork can still rebase onto upstream.
- Workspace path containment and key sanitization are security boundaries and must not weaken.
- `Reload()` stays fail-safe.

## Goals / Non-Goals

**Goals:**

- When the environment is `smolvm`, no code from the workspace or the agent runs on the host. That includes `git` reading a guest-controlled repository.
- An agent kind runs in the VM with no change specific to that kind. Adapters keep building commands as they do today. The environment supplies the carrier.
- Sortie's MCP tools work inside the VM. Tracker credentials stay on the host.
- The `local` kind behaves exactly as today. Its tests pass unchanged.

**Non-Goals:**

- Running the environment on a remote host. smolvm runs where Sortie runs.
- Combining `smolvm` with `worker.ssh_hosts`.
- Graceful agent shutdown inside the VM. smolvm delivers no TERM. Session teardown relies on the existing stop flow, then on stopping the VM.
- Agents pushing or opening pull requests from inside the VM. Under smolvm with a `repository`, only Sortie talks to the git host (decisions 14 to 17).
- Hosting stack packs in a registry, warm VM pools, and checkpoints.

## Decisions

### 1. An environment adapter family, resolved by kind

Add `internal/environment` with a small interface. Kinds register in `init()`, as tracker and agent kinds do: `internal/environment/local` and `internal/environment/smolvm`. The orchestrator resolves the kind through `internal/registry`, and `cmd/sortie` blank-imports both.

The interface:

- `Prepare(ctx, ws)`: make the issue's environment ready to run commands, and report whether it was created just now. That report replaces `EnsureResult.CreatedNow` for deciding when `after_create` runs.
- `Command(ctx, ws, spec)`: return an `*exec.Cmd` that runs argv in the workspace, with the given environment entries, inside the environment. `spec` names the argv, the working directory relative to the workspace, the env, and whether stdin stays open.
- `Release(ctx, ws)`: the worker for this issue has exited. smolvm stops the VM here; `local` does nothing.
- `Remove(ctx, ws)`: delete the environment. Called where Sortie removes a workspace today.
- `Sweep(ctx, keep)`: delete environments that Sortie owns but no known workspace references.

`ws` carries the workspace key, the host path, the guest path, the issue ID and the identifier.

`local` implements `Command` as today's `exec.Command`, with `cmd.Dir` set to the host workspace. Every other method is a no-op, so behavior is unchanged.

**Alternative considered: extend `LaunchTarget` only.** That covers the agent launch, but not hooks, verification, triage, or git inspection. It would leave the host-execution gap the proposal exists to close.

**Configuration:**

```yaml
environment:
  kind: smolvm            # local (default) | smolvm
  host_prefix: [acp-broker, -http, 127.0.0.1:7701, --]   # optional
  smolvm:
    binary: smolvm        # optional, resolved once at startup
    pack: /var/lib/smol-builder/myproject.smolmachine
    cpus: 4
    memory_mib: 8192
    storage_gib: 20
    allow_hosts: [openrouter.ai, models.opencode.ai, registry.npmjs.org]
    credentials:
      - {name: openrouter, env: OPENROUTER_API_KEY, hosts: [openrouter.ai]}
    repository:           # optional; decisions 14 to 17
      url: git@github.com:org/app.git   # fetched and pushed by the host, with the host's credentials
      base: main
      branch_prefix: sortie/            # issue branch = prefix + workspace key
      provider: github                  # SCM adapter that opens pull requests; optional
      project: org/app                  # owner/repo for that adapter; required with provider
      max_bundle_mib: 512
    pass_env: []          # host variables copied into the guest in plain text, opt-in
    ssh_agent: false
```

Changes to `environment` apply to environments created after a reload. A running VM keeps the settings it was created with. A reload that fails validation keeps the previous config, as `Reload()` does today.

### 2. The agent launch: the environment supplies the carrier, adapters stay unchanged

`ResolveLaunchTarget` gains one more input: the environment's launch carrier. For `smolvm` it yields a remote target, as SSH does, but with a different carrier:

```
<host_prefix...> smolvm machine exec --name <vm> -i -w <guest ws> -e K=V... [--secret-env N=N...] -- <agent argv>
```

Adapters call `sshutil.BuildSSHLaunch` directly at five sites: opencode, codex, clientprotocol, `agentcore.forkperturn` (claude-code and copilot), and `LaunchTarget.AuxiliaryCommand`. Those calls move behind one `LaunchTarget.RemoteLaunch(argv, opts)` method. That method returns the SSH carrier or the smolvm carrier. This is the only edit at those sites, and SSH behavior does not change.

The checks for a failed SSH connection, which match `sshutil.ConnectionFailed` on exit 255, get a smolvm counterpart in the same place. It classifies a VM that is not running, or a CLI that fails before the guest command starts, as a connection failure. Those failures keep today's retry semantics.

**Splitting "remote" into two flags.** The meaning adapters attach to "remote" splits into:

- `Remote`: the binary is not on this host, so skip local canaries and `exec.LookPath`. SSH and smolvm both set it.
- `MCPInGuest`: the MCP config Sortie generated is valid inside the target, so pass it to the agent. Only smolvm sets it.

Today's remote MCP behavior is kept for SSH by leaving `MCPInGuest` false. Adapters use the MCP config in one of two ways.

- **They parse the file on the host and inline it.** These are opencode `translateMCPServers`, clientprotocol `parseMCPServers`, and the codex override block. Each tests "remote" today. That test becomes `Remote && !MCPInGuest`. Parsing still reads the host copy.
- **They pass the file's path to the runtime.** These are claude-code `--mcp-config` and copilot `--additional-mcp-config @path`. Inside the VM the runtime needs the guest path. So these two pass `target.GuestPath(state.mcpConfigPath)`, which maps `<host ws>/.sortie/x` to `<guest ws>/.sortie/x` under smolvm. Under every other carrier it returns the path unchanged.

This works because the control directory is the same directory on both sides (decision 6).

**Alternative considered: a shell preamble on stdin, as SSH carries env.** That breaks with `host_prefix`. A broker relays stdin as JSON-RPC and would choke on the preamble. smolvm's `-e` and `--secret-env` carry the values without stdin, so they are used instead.

### 3. What reaches the guest environment

- **Session identity**, passed with `-e`: `SORTIE_ISSUE_ID`, `SORTIE_ISSUE_IDENTIFIER`, `SORTIE_DISPATCH_ID`, `SORTIE_ATTEMPT`, `SORTIE_RULE`, `SORTIE_CHAIN_ID`, `SORTIE_SESSION_PURPOSE`, and `SORTIE_WORKSPACE` set to the guest path. These are not secrets.
- **Never carried:** `SORTIE_SESSION_TOKEN` and `SORTIE_API_URL`. The guest cannot reach the host loopback API anyway, so a value there would only invite a confusing failure. A host prefix, such as the broker, runs on the host and still receives both.
- **`pass_env` names**, passed with `--secret-env NAME=NAME`, so the values are not in host argv. This is plain text in the guest by explicit opt-in.
- **Credentials:** only through credential bindings. The guest sees the placeholder in the bound variable.
- **Agent-declared credential variables** (the kind's own list, as used for SSH): if one is set on the host and is covered by neither a binding nor `pass_env`, dispatch preflight fails and names the variable. Sortie never silently copies it into the guest, and never silently drops a variable the agent needs.

### 4. `host_prefix` keeps part of the command on the host

When it is set, Sortie runs `host_prefix + <carrier + agent argv>` as the local process. The prefix inherits the full host session environment, including the session token. This realizes the acp-broker design, where the broker runs on the host and only the agent runs in the VM.

`host_prefix` applies only to the agent session launch and the credential check. It does not apply to hooks or auxiliary commands. With `local` it is concatenated in front of the agent command, which is equivalent to today's prefixing of `agent.command`.

### 5. One VM per issue workspace, stopped between runs

**The VM tracks the workspace.** The VM's name is `sortie-<workspace key>`. The workspace key is already sanitized to a safe charset. A name longer than smolvm accepts is truncated, and a short hash of the full key is appended. Labels record ownership:

- `sortie.managed=1`
- `sortie.workspace=<key>`
- `sortie.pack=<sha256 of the pack file>`
- `sortie.workflow=<hash of the workflow path>`

The VM's lifecycle follows the workspace's:

- **`Prepare`:** if no VM exists, it creates one from the pack (`machine create --from`) with the configured resources, allowlist, credentials, and mounts, then starts it. It reports "created now", so `after_create` runs. If the VM exists but is stopped, it starts it. A failure to create or start fails workspace preparation. That failure is retried like any other preparation error.
- **`Release`** (worker exit): `machine stop`. A stopped VM holds no RAM, and starting it again takes about 0.7 s. Its disk, and so the workspace, persists.
- **`Remove`** (workspace cleanup: terminal state, retention sweep, `CleanupByPath`): run `before_remove` in the VM, then `machine delete -f`, then remove the host workspace directory. That last step is the cleanup that already happens today.
- **`Sweep`** (startup and the periodic retention sweep): `machine ls --json`. Any VM labeled `sortie.managed=1` for this workflow whose workspace directory no longer exists is deleted. A VM is never deleted while a worker for its issue runs.

**Alternatives considered:**

- **A fresh VM per dispatch.** It discards the warm workspace and the agent's session continuity across retries, and it breaks `after_create` semantics.
- **Leaving VMs running.** Five idle VMs cost about 1.5 GiB for no benefit.

### 6. The guest workspace and the shared control directory

**The workspace lives on the VM's own disk.** The guest workspace is `/workspace`. With `repository` set, Sortie seeds it from a bundle before `after_create` runs (decision 14). Without it, `after_create`, which now runs in the guest, must obtain the code itself. Code never sits on a host mount. A mount would be 8x slower, and it would put guest-planted symlinks and setuid files on the host.

**Only the control directory is shared.** The host keeps the per-issue workspace directory at `<workspace.root>/<key>`, as today. Sortie creates its `.sortie` subdirectory before the VM exists, and mounts it read-write at `/run/sortie/control`.

After `after_create` succeeds, Sortie runs `ln -s /run/sortie/control /workspace/.sortie` in the guest. The link is not mounted directly at `/workspace/.sortie` because `/workspace` must be empty when `after_create` runs: hooks commonly run `git clone <url> .`, and seeding clones into it too. Today, too, the host `.sortie` appears only after `after_create`.

A repository that commits its own `.sortie` entry fails preparation with an error that names it, and Sortie never overwrites that entry. The spike verified that a mount nested on the guest disk shares writes both ways.

Every control file then keeps one path on each side:

- The agent writes `status`, `scm.json`, and `review_verdict.json` in the guest. Sortie reads them on the host through `workspacekit`, unchanged.
- Sortie writes `mcp.json`, `state.json`, and `review_summary.md` on the host. The agent reads them in the guest.

No `workspacekit` code changes, and the trust model doesn't change either. That directory was already treated as hostile input: Sortie opens it through `os.Root`, refuses links, and caps sizes.

`SORTIE_WORKSPACE` is `/workspace` for every process in the guest. The host workspace path appears only in host-side logs and in `/api/v1/state`. The state output gains an `environment` field naming the VM.

**Three host mounts in total.** Exactly three host resources are given to the VM:

1. this `.sortie` directory;
2. the tool-server socket (decision 9);
3. a read-only directory holding only the Sortie binary (decision 9).

`--nested`, `--allow-system-mounts`, `--docker-socket`, ports, and any other `-v` mount are never used.

### 7. Git inspection runs in the guest

**What moves into the guest.** `handoff_evidence` and the self-review diff run the same git commands they run today, through `Environment.Command`, in the guest workspace. Sortie reads their stdout as bytes, with the same caps.

The fingerprint hashes the same three command outputs. For untracked files, the host currently reads each file's contents. Instead, the guest runs `git hash-object --stdin-paths` over the `ls-files --others` list. The fingerprint becomes a hash of those object IDs.

**What a malicious repository can still do.** A planted fsmonitor, filter, or textconv can still run, but only in the guest, where the agent can already run anything. What it can do there is lie about its own evidence. That is no worse than today, since the agent already controls the work tree.

**Alternatives considered:**

- **Hardened host git** (`-c core.hooksPath=/dev/null -c core.fsmonitor= --no-textconv`, `safe.directory`). It reduces the surface, but it is a denylist against git's growing config surface. It also needs the work tree on the host, which the guest workspace rules out.
- **Hardened host git against the guest repository.** Rejected for the same reason. Moving work out uses bundles imported into a host-owned mirror instead (decision 15), where host git never reads a guest-controlled `.git`.

### 8. Hooks, verification, and triage run in the guest

**Hooks and verification.** `RunHook` and self-review verification take an `Environment` and build their command with `Command(ctx, ws, {argv: ["sh", "-c", script], env})`. Their timeout and teardown stay on the host side. Cancelling kills the `smolvm` CLI, and the spike verified that this kills the guest process group. Hooks receive `SORTIE_ENVIRONMENT=smolvm` in addition to today's variables.

**Triage.** Reaction triage writes its input file into the guest's tmpfs instead of a host temporary directory. That path is `/run/sortie/triage/<run id>/input.json`, written by piping it through `Command` with `cat`. Triage reads the result back with `head -c <cap>`. The guest's `/run` is tmpfs, so leftovers vanish when the VM stops, and the externally authored text stays out of the workspace tree, as the host design intended.

**After seeding, `after_create` is setup only.** With `repository` set, the code is already in `/workspace` when `after_create` runs, so the hook installs dependencies and similar. It cannot reach the git host, because nothing on the allowlist names it.

### 9. Sortie tools reach the host through a socket

**The host side.** For a VM workspace, Sortie listens on a host Unix socket at `<state dir>/env/<key>/tools.sock`. `<state dir>` sits next to the database, outside the workspace. The socket is mounted into the guest at `/run/sortie/tools.sock`.

On each connection, Sortie starts the same `sortie mcp-server --workflow ...` subprocess an agent would start today. It runs on the host, with the session's env block, and its stdin and stdout are bridged to the connection. The tool server, its tracker credentials, and the database never enter the guest.

**The guest side.** The generated `mcp.json` names `/opt/sortie/sortie mcp-relay /run/sortie/tools.sock`. `/opt/sortie` is a read-only mount of a host directory holding only a copy of the running Sortie binary. Sortie is static and the guest has the same architecture, so the binary runs as is. `mcp-relay` is a new, tiny subcommand that copies stdin and stdout to the socket.

**Failure handling.**

- With no listener, a guest connect succeeds and then reads EOF. That was observed in the spike. `mcp-relay` reports "tool server unavailable" on stderr and exits non-zero, so the agent sees a failed MCP server and not a hang.
- After a Sortie restart, the listener is recreated at the same path. The spike verified that a running VM reaches the new listener without a restart.

**Alternatives considered:**

- **Running `sortie mcp-server` in the guest.** It would need the workflow file, tracker credentials, and database access inside the VM, which defeats the boundary.
- **`socat` from the stack image.** It would make every stack depend on a tool Sortie can't pin.
- **An HTTP MCP endpoint.** Guest egress to the host loopback is blocked by design.

### 10. Driving smolvm: one small CLI client, pinned version

`internal/environment/smolvm` wraps the CLI in one place. It is the only code that knows smolvm's flags, its JSON output, or its exit codes.

At startup, and on any reload that selects `smolvm`, Sortie runs `<binary> --version` once and checks the result against a supported range, initially exactly `1.26.x`. On a mismatch, startup fails, or the reload is rejected and the previous config kept. The error names the found and the supported version. The range widens only after the spike checks are re-run against a new release.

These are read as JSON (`machine ls --json`): whether a VM exists, its state, its labels, and which VMs are leftovers. A failed `smolvm` invocation becomes an error carrying its exit code and the last 8 KiB of stderr, the same tail size hooks keep.

**Alternative considered: the HTTP API (`smolvm serve`).** It needs a daemon to supervise, its WebSocket exec has the frame bug, and it takes credential values only through an extra API call. The CLI needs none of that. The cost is about 90 ms of process start per exec, which is negligible next to agent turns.

### 11. The pack is a file; the VM remembers which one it came from

**One file per workflow.** `environment.smolvm.pack` names a `.smolmachine` file on the Sortie host. Sortie checks that it exists and is readable at startup and on reload. It records the file's SHA-256 in the new VM's `sortie.pack` label and in the run history row of every run.

**What a rebuilt pack affects.** `smol-builder build` rewrites the file in place. Rewriting it affects only VMs created after the rewrite. Existing VMs keep the base they were created from: smolvm caches pack extractions by content. To move an issue onto a new pack, remove its workspace.

**Alternative considered: registry references pinned by digest.** These are better for sharing between hosts. The spike found that smolvm's pack VM cannot pull from a registry on the host's loopback, and we run one host. Deferred.

### 12. `smol-builder`: a separate tool in its own repository

The new repository `~/dev/smol-builder` holds:

- `cmd/smol-builder`: Go, no CGo, a single binary.
- `layers/`: the layer library. `base`, `go`, `node`, `python`, and `rust` are ported from the spike with the same pins.

A project declares its stack in its own repository, in `smol-builder.toml` at the root:

```toml
layers = ["go", "node"]          # names from the layer library
project_layer = "ci/agent.Dockerfile"   # optional, applied last
```

`smol-builder build --repo <dir> --output <file>.smolmachine [--layers <dir>]` does the following:

1. Applies layers in sorted order, then the project layer.
2. Tags each image by a content hash of the chain.
3. Exports the image and boots a builder VM with the image's `Env` and `WorkingDir` passed as `-e` and `-w`.
4. Runs `pack create --from-vm`.
5. Writes the output atomically: it writes a temporary file and renames it into place.
6. Prints a JSON report: layers, image tag, pack SHA-256, sizes, and timings.

The base layer installs agents but no credentials, and its opencode config holds only policy.

**Why a separate tool.** It keeps podman out of Sortie's dependencies and out of the fork's diff. It also lets CI or a developer build packs without running Sortie.

**Why Go, not the spike's Python.** It is the same toolchain and test style as the fork, and a single binary to install. It runs `podman` and `smolvm` as subprocesses, as the spike did.

**Alternative considered: Sortie builds packs from `smol-builder.toml` on demand.** The user rejected it. It would add a container-engine dependency, and build failures, to dispatch.

### 13. Switching a workflow's environment kind is a cold restart per issue

`Prepare` writes `.sortie/environment`, holding the kind and the VM name, when it creates an environment. When it finds an existing workspace whose recorded kind differs from the configured one, it treats the workspace as stale:

1. It runs that kind's `Remove`.
2. It deletes the host directory.
3. It prepares from scratch, so `after_create` runs again.

A workspace with no record is one created before this change, and counts as `local`. Without this rule, switching from `smolvm` back to `local` would leave an existing host directory that holds only `.sortie`. The agent would start in an empty tree and `after_create` would not run.

### 14. A host-owned mirror seeds and refreshes the guest

**The mirror.** For each distinct `repository.url`, Sortie keeps a bare repository at `<state dir>/repos/<sha256(url)[:16]>.git`. Only Sortie writes it. It holds:

- `refs/heads/*`, fetched from the upstream with `--prune`;
- `refs/sortie/incoming/<key>`, one ref per issue, written only by the import (decision 15);
- `refs/sortie/pushed/<key>`, the last commit Sortie pushed for that issue.

Every host git command on the mirror runs with `-c core.hooksPath=/dev/null -c core.fsmonitor=false -c transfer.fsckObjects=true`. Operations on one mirror are serialized by an exclusive lock file next to it. Host git here is safe because the mirror is never a work tree and no guest process ever writes it: objects arrive only through `git fetch` from a bundle, with every object checked.

The host's own git configuration and credentials (SSH agent, credential helper) are used for the upstream. They never reach the guest.

**The issue branch.** It is `branch_prefix` plus the workspace key, for example `sortie/ENG-42`. Sortie checks it with `git check-ref-format --branch`. An invalid name fails preparation with the name in the error.

**Moving bundles across the boundary.** A bundle crosses only through `Environment.Command`:

- in: the host pipes it to `cat > /run/sortie/git/in.bundle`;
- out: the host reads `cat /run/sortie/git/out.bundle` and stops at `max_bundle_mib`.

No file copy API and no shared mount is involved. `/run` is tmpfs in the guest, so bundles never land in the workspace.

**Seeding a new workspace.** Before `after_create`:

1. Sortie fetches the upstream into the mirror. A failure here fails preparation.
2. It creates a bundle of `refs/heads/<base>`, plus `refs/heads/<issue branch>` when that exists upstream.
3. It sends the bundle into the guest.
4. The guest runs `git clone --origin origin /run/sortie/git/in.bundle /workspace`.
5. The guest checks out the issue branch: from `origin/<issue branch>` when it exists, else as a new branch at `origin/<base>`.
6. The guest sets `origin`'s URL to `repository.url`, so tools show the real remote. The guest still cannot reach it.

**Refreshing before each later run.** In `Prepare`, for an existing VM, Sortie fetches the upstream and sends the same two refs. The guest runs `git fetch /run/sortie/git/in.bundle '+refs/heads/*:refs/remotes/origin/*'`. The agent's branch and work tree are untouched, but `origin/main` and `origin/<issue branch>` are current. So a merge-conflict reaction can rebase, and commits a human pushed to the branch are visible. If the upstream fetch fails on refresh, Sortie logs a warning and continues with the mirror's last state.

**Alternative considered: the guest clones upstream itself.** It needs egress to the git host and a read credential in the guest. The user chose option 2 to avoid both.

### 15. Export: import exactly one ref, never touch a guest `.git`

The export runs at the end of every run that ended normally, after `after_run` and before the tracker handoff:

1. **Bundle in the guest.** The guest runs `git bundle create /run/sortie/git/out.bundle refs/heads/<issue branch>`. A missing branch means nothing to export.
2. **Read it out.** Sortie reads the bundle as bytes, up to `max_bundle_mib`, into a file in the host state directory. A larger bundle fails the export.
3. **Check the heads.** `git bundle list-heads` must name exactly `refs/heads/<issue branch>`, and nothing else.
4. **Import.** `git fetch <bundle> refs/heads/<issue branch>:refs/sortie/incoming/<key>` runs in the mirror, with the safe configuration.
5. **Skip when there is nothing new.** If the incoming commit equals the upstream branch tip, or equals the base when the branch does not exist upstream, there is nothing to push. The export succeeds with no push.

**Only committed work is exported.** Uncommitted changes stay in the guest workspace for the next run. The handoff evidence still reports a changed work tree as today.

**Alternatives considered:**

- **Auto-commit of uncommitted work** (homelab did a WIP commit). Rejected: it puts commits the agent didn't make on the branch, and it is easy to add later as a guest hook.
- **Reading `.git` objects through the shared mount.** Rejected: that is the escape class this change closes.

### 16. Push: the host's credentials, never over someone else's commits

Sortie pushes with `git push <url> refs/sortie/incoming/<key>:refs/heads/<branch> --force-with-lease=refs/heads/<branch>:<expected>`. `<expected>` is:

- `refs/sortie/pushed/<key>` when Sortie pushed this branch before;
- the empty value (branch must not exist) when it did not.

The rules that follow from that lease:

- **Agent rebases are allowed.** Sortie's own earlier push can be replaced.
- **Commits someone else pushed since Sortie's last push are never overwritten.** The lease fails. The export reports `branch moved upstream`, and the run fails. The next run's refresh brings that commit into the guest as `origin/<branch>`, so the agent can integrate it.

After a successful push, Sortie updates `refs/sortie/pushed/<key>`. It records the commit and the push time in the run history and in the trusted SCM record (decision 17).

**A failed export fails the run.** That covers any step of decisions 15 and 16. The run is reported as failed with an export error and retried with the normal backoff. The tracker is not transitioned. The VM and its workspace are kept, so the committed work is still there for the retry.

**Alternative considered: always force-push.** Rejected: a human's commit on the branch would be silently lost.

### 17. Sortie opens the pull request and owns the SCM record

**Opening the pull request.** `domain.PullRequestOpener` is a new optional interface, alongside `AutoMergeScopeVerifier`:

```go
EnsurePullRequest(ctx, owner, repo, head, base, title, body string) (PullRequest{Number int, URL string, Created bool}, error)
```

It returns the open pull request whose head is `head`, when one exists. Otherwise it creates one. The GitHub, GitLab (merge requests), and Gitea adapters implement it. `SCMAdapter` itself is unchanged, so no other implementer or test fake breaks.

**When it runs.** After a push, when `repository.provider` is set, Sortie calls it with:

- `head`: the issue branch;
- `base`: `repository.base`;
- `owner/repo`: from `repository.project`.

`provider` must equal the provider of every active SCM reaction, the same rule Sortie already applies across reactions. The adapter is built from the same configuration block those reactions use. A provider whose adapter lacks the interface fails validation.

**Title and body.** The agent may suggest them in `.sortie/pr.json`: `{"title": "...", "body": "..."}`. That is agent-authored text, so Sortie:

- reads it through `workspacekit`, capped at 64 KiB;
- strips control characters other than newline and tab;
- cuts the title to 256 characters.

Without the file, the title is `<identifier>: <issue title>` and the body links the issue. Sortie never runs the text through a shell. A failure to open the pull request fails the export.

**The trusted SCM record.** Under smolvm with `repository`, Sortie writes the SCM record itself to `<workspace.root>/<key>/.sortie-host/scm.json`. That directory is host-only: it is not under the shared `.sortie`, and the guest has no path to it. The record has `branch`, `sha`, `pushed_at`, `pr_number`, `owner`, and `repo`. Every reader of SCM metadata (CI, review, bot review, auto-merge, merge conflicts, label commands, startup recovery) reads this record and ignores `.sortie/scm.json`.

Otherwise an agent could write a different `pr_number` and point CI polling, reviews, or auto-merge at another pull request.

**Alternative considered: an operator export hook running `gh pr create`.** The user chose the adapter method: there is no script to maintain, and the forge credentials and error mapping Sortie already has are reused.

## Risks / Trade-offs

- **[smolvm churns fast, with one main maintainer]** → Pin the version range (decision 10). Keep every smolvm detail in one package. Keep the spike scripts as a re-validation suite to run before widening the range.
- **[No graceful TERM inside the VM]** Sortie's stop flow sends SIGTERM to the launch's process group. Under smolvm that ends the CLI, and the CLI ends the guest command at once, so `agent.stop_grace_ms` gives the agent no time to shut down cleanly. → Accept it for this change. In-flight output is lost. The agent's own session state lives on the guest disk and survives for `ResumeSessionID`. The tasks measure what an agent loses when stopped mid-turn. A guest-side TERM relay is a follow-up if that loss matters.
- **[TLS interception for credentials]** Some clients carry their own trust store, which may be the case for the Rust codex binary. → Verify each agent kind in the VM before claiming support: opencode is verified, and claude-agent-acp and codex are checked in the tasks. An unsupported kind fails its credential check visibly instead of leaking a key. Other limits apply on credential hosts: HTTP/1.1 only, no WebSocket upgrade, and request bodies capped at 8 MiB.
- **[Exfiltration to allowed hosts]** An agent can still send data to any host on the allowlist, such as a package registry. With `repository` set, the git host needs no entry, so git is not an exfiltration path. → The allowlist is policy, and the default is empty. Operators see denials with `smolvm machine egress-events --name <vm>`. The VM name appears in `/api/v1/state`.
- **[The shared `.sortie` mount can fill the host disk]** → Sortie never reads past its caps. Disk use is bounded by the workspace root's filesystem, as today. Not mitigated further in this change.
- **[Tools reachable by any guest process]** → Same as today: every process the agent starts can already reach the tools. The socket is per issue, and the tool server it starts is scoped to that issue's session env.
- **[Everything the agent commits reaches the upstream]** Sortie pushes any commit on the issue branch, including changes to CI configuration or to the repository's own sandbox setup. → Branch protection on the base branch stays the gate for merging. Path-based export policy is out of scope, and a follow-up if needed.
- **[Host push credentials]** Sortie pushes with the operator's git credentials, which may reach more than this repository. → They never enter the guest, and the only ref Sortie pushes is the issue branch. Prefer a deploy key or a token scoped to the repository.
- **[Bundle-based refresh costs time]** Each run fetches upstream and sends a bundle of two branches. → Bundles of a whole branch history can be large for big repositories; `max_bundle_mib` bounds the output side. Incremental bundles (`base..branch` with prerequisites) are a later optimization that changes no spec.
- **[The pack extraction cache grows]** It reached 9.8 GiB in the spike. → Document `smolvm pack prune` in the smolvm environment guide.
- **[KVM unavailable]** → The startup check fails with smolvm's own message, and Sortie does not start.

## Migration Plan

1. Install smolvm 1.26.x on the host. Build a pack with `smol-builder build` for the project.
2. In one workflow, set `environment.kind: smolvm`, along with `pack`, `allow_hosts`, `credentials`, and `repository`. Remove the clone from `after_create`, and remove push and pull-request steps from the prompt and hooks; Sortie does both.
3. Existing issue workspaces are recreated on their next dispatch (decision 13).
4. **Rollback:** set `environment.kind: local`, and restore the clone in `after_create` and the push and pull-request steps the agent did before. Workspaces are recreated on the host on their next dispatch, and leftover VMs are swept. Branches and pull requests Sortie created stay upstream.

The default stays `local`, so a workflow that doesn't set `environment` sees no change.

## Open Questions

- Whether different rules should use different packs or VM sizes, for example a smaller VM for review. This is an additive key under `environment.smolvm` later, and does not change this design.
- Whether Docker-in-VM setup belongs in a `docker` layer of the library or in a project layer. Neither is needed in this change.

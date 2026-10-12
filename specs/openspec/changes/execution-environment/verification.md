# Verification: execution-environment

## Task group 1: remaining smolvm checks

Run on 2026-10-12 with smolvm 1.26.1 on the Sortie host (CachyOS, KVM). Every machine was created for these checks only, labeled `sortie.test=execution-environment`, and deleted by that label afterwards. The packs are the spike's, from `spikes/smolvm/golden/out/` on branch `spike/smolvm`: `base-639f67207fb8f11d.smolmachine` (opencode 1.18.29) and `go-node-ce57b820f0d118fb.smolmachine` (adds Node 24.21.0). The scratch harness is in `/tmp/opencode/ee`.

In the commands below, `S` is a shell function for `smolvm machine exec --name <machine> -- "$@"`.

### Task 1.1: three mounts on one machine

The Sortie binary was built from the fork with `CGO_ENABLED=0 go build ./cmd/sortie` and copied into a host directory of its own. A small Python listener on the host answered each connection with `host-echo:` plus what it read.

```sh
smolvm machine create --name ee-s11 --from base-639f67207fb8f11d.smolmachine \
  --label sortie.test=execution-environment \
  -v /tmp/opencode/ee/s11/control:/run/sortie/control \
  -v /tmp/opencode/ee/s11/opt:/opt/sortie:ro \
  --mount-socket /tmp/opencode/ee/s11/tools.sock:/run/sortie/tools.sock
smolvm machine start --name ee-s11      # "Starting machine 'ee-s11' with 2 mount(s)..." in 0.31 s
```

**The binary runs from the read-only mount.**

```text
$ S /opt/sortie/sortie --version
sortie dev (commit: unknown, built: unknown, go1.27.1-X:nodwarf5, linux/amd64)
rc=0
```

**Guest writes to `/opt/sortie` fail, and the host enforces it.** The guest is root. A remount reports success but changes nothing, and a fresh mount of the same virtiofs tag is read-only too:

```text
$ S sh -c 'echo x > /opt/sortie/planted; touch /opt/sortie/sortie'
sh: 1: cannot create /opt/sortie/planted: Read-only file system
touch: cannot touch '/opt/sortie/sortie': Read-only file system
$ S sh -c 'mount -o remount,rw /opt/sortie; echo rc=$?; echo x > /opt/sortie/planted'
rc=0
sh: 1: cannot create /opt/sortie/planted: Read-only file system
$ S sh -c 'mkdir -p /mnt/x && mount -t virtiofs smolvm1 /mnt/x; echo z > /mnt/x/planted3'
sh: 1: cannot create /mnt/x/planted3: Read-only file system
$ ls /tmp/opencode/ee/s11/opt
sortie
```

**The control link shares writes both ways.**

```text
$ S sh -c 'ls -A /workspace'                  # empty before the link
$ S sh -c 'ln -s /run/sortie/control /workspace/.sortie && echo guest-wrote > /workspace/.sortie/status'
$ cat control/status                           # on the host
guest-wrote
$ echo host-wrote > control/mcp.json; S cat /workspace/.sortie/mcp.json
host-wrote
$ S ln -sf /etc/passwd /workspace/.sortie/evil; readlink control/evil   # host
/etc/passwd
```

Guest files show uid 1000 inside the guest and belong to the host user on the host. A symlink the guest plants appears on the host as a symlink, which is what `workspacekit` refuses.

**The socket reaches the host listener**, tested with `perl` and `IO::Socket::UNIX`, since the base image has no `python3`, `nc` or `socat`:

```text
with listener:        read n=15 data=[host-echo:ping]
listener killed:      connected; wrote=5; read n=undef err=Connection reset by peer
socket file removed:  connected; read n=undef
listener restarted:   read n=15 data=[host-echo:ping]
```

**Result.** All three checks pass. Two details differ from what the design records, and neither changes it:

- With no listener, the guest's connect succeeds, and the first read fails with `ECONNRESET`, not a clean EOF. `mcp-relay` must therefore treat a read error before the first response byte the same as EOF: both mean `tool server unavailable`.
- `machine ls --json` reports `"mounts": 2`. The socket is not counted as a mount, and `machine ls` shows no mount paths. The proof of "exactly three resources" is the `create` argv that Sortie builds, which the unit tests assert.

The guest's `mount` table also lists the `-v` mounts again under `/storage/overlays/<vm>/merged/...`, one of them flagged `rw`. Writes through that path fail with `Read-only file system` too.

### Task 1.2: claude-agent-acp and codex behind a credential binding

There is no Anthropic or OpenAI key on this host, so both agents used OpenRouter's compatible endpoints, with the OpenRouter key bound to `openrouter.ai`. The host variable was exported under the name each agent reads; the guest saw only the placeholder.

```sh
export ANTHROPIC_AUTH_TOKEN="$OPENROUTER_API_KEY" OPENAI_API_KEY="$OPENROUTER_API_KEY"
smolvm machine create --name ee-s12 --from go-node-ce57b820f0d118fb.smolmachine \
  --label sortie.test=execution-environment \
  --allow-host-pattern registry.npmjs.org --allow-host-pattern openrouter.ai \
  --credential anthropic=ANTHROPIC_AUTH_TOKEN@openrouter.ai \
  --credential openai=OPENAI_API_KEY@openrouter.ai
smolvm machine start --name ee-s12
```

The guest environment, with the placeholders shortened:

```text
CURL_CA_BUNDLE=/run/smolvm/ca-bundle.pem
NODE_EXTRA_CA_CERTS=/run/smol/credentials/ca.pem
SSL_CERT_FILE=/run/smolvm/ca-bundle.pem
REQUESTS_CA_BUNDLE=/run/smolvm/ca-bundle.pem
DENO_CERT=/run/smol/credentials/ca.pem
ANTHROPIC_AUTH_TOKEN=SMOL_PLACEHOLDER_...
OPENAI_API_KEY=SMOL_PLACEHOLDER_...
```

**claude-agent-acp 0.89.1.** It was installed in the guest with `npm i -g @agentclientprotocol/claude-agent-acp@0.89.1`. That pulls `@anthropic-ai/claude-agent-sdk-linux-x64`, the native Claude Code binary. The ACP driver (`/tmp/opencode/ee/acp_drive.py`) ran it over `machine exec -i`:

```sh
python3 acp_drive.py ee-s12 /workspace/repo "Reply with exactly the word pong. Do not use any tools." \
  --env ANTHROPIC_BASE_URL=https://openrouter.ai/api --env ANTHROPIC_API_KEY= \
  --env ANTHROPIC_MODEL=anthropic/claude-haiku-5.5 --env ANTHROPIC_SMALL_FAST_MODEL=anthropic/claude-haiku-5.5 \
  --env CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 -- claude-agent-acp
```

```text
[  0.22s] initialize: {"protocolVersion": 1, "agentCapabilities": {..., "loadSession": true, ...
[  0.54s] session/new: 599fc062-c81a-4bc9-a653-373510cbe4bc
pong
[  3.79s] prompt result: {"jsonrpc": "2.0", "id": 3, "result": {"stopReason": "end_turn", "usage": {"inputTokens": 2, "outputTokens": 4, ...
[  3.85s] exit: 0
$ smolvm machine egress-events --name ee-s12
No egress denials recorded for 'ee-s12'.
```

**codex-cli 0.154.0.** The host's static binary was copied in with `smolvm machine cp` (251 MB at about 85 MB/s) and run once with `codex exec`:

```sh
S codex exec --skip-git-repo-check -c model_provider=openrouter \
  -c 'model_providers.openrouter={name="openrouter",base_url="https://openrouter.ai/api/v1",env_key="OPENAI_API_KEY",wire_api="responses"}' \
  -m anthropic/claude-haiku-5.5 "Reply with exactly the word pong. Do not run commands."
```

```text
provider: openrouter
...
codex
pong
tokens used
15,267
```

codex also tried `api.github.com`, `chatgpt.com` and `ab.chatgpt.com`. `egress-events` lists those as denied, and the turn succeeded anyway.

**The key never reached the guest.** The guest searched every process environment and `/root`, `/workspace`, `/tmp`, `/etc`, `/opt` and `/run` for OpenRouter key-shaped strings (`sk-or-v1-[0-9a-f]*`), and printed only a SHA-256 prefix of each match, so the check itself put no key bytes in argv. The host key's prefix is `f8b504d480920a41`. The guest found no match at all:

```text
procdone
filesdone
```

**Result.** Both clients accept the substituted certificate. claude-agent-acp's native binary (Bun) reads `NODE_EXTRA_CA_CERTS`, and codex's Rust client reads `SSL_CERT_FILE`. This matches the design. The guide's support list:

| Agent kind | Under smolvm |
|---|---|
| `agent-client-protocol` with `opencode acp` | Supported (spike, 2026-10-11) |
| `agent-client-protocol` with `claude-agent-acp` | Supported (this check) |
| `codex` | TLS works (this check). The kind's own `app-server` launch was not run in a VM. |
| `claude-code`, `copilot`, `pi` | Not verified |

### Task 1.3: SIGTERM to `smolvm machine exec` in the middle of an opencode turn

```sh
smolvm machine create --name ee-s13 --from base-639f67207fb8f11d.smolmachine \
  --label sortie.test=execution-environment \
  --allow-host-pattern openrouter.ai --allow-host-pattern models.opencode.ai \
  --allow-host-pattern registry.npmjs.org \
  --credential openrouter=OPENROUTER_API_KEY@openrouter.ai
python3 acp_drive.py ee-s13 /workspace/repo "First run the shell command 'sleep 25' with the bash tool. After it finishes, create the file done.txt containing the word done." \
  --kill-after 12 -- opencode acp
```

The driver sent SIGTERM to the `smolvm machine exec` process 12 s after `session/prompt`, while the `sleep 25` tool call was running:

```text
[  1.71s] session/new: ses_ed097006affeBzSwGFL5TCXtoq
[  3.41s] update tool_call: bash
[ 13.71s] SIGTERM -> smolvm exec pid 1358454
[ 13.71s] EOF waiting for session/prompt; exit=-15 stderr tail: []
$ S ps -eo pid,args
    1 /run/smolvm/init container-init
   17 [opencode] <defunct>
```

The CLI died of the signal at once, stdout closed with no `session/prompt` response, and no stderr was written. In the guest, `opencode` was a zombie and its `sleep` was gone.

A new `opencode acp`, started with `session/load` of the same session, replayed:

```text
{"sessionUpdate": "user_message_chunk", "content": {"type": "text", "text": "First run the shell command 'sleep 25' ..."}}
{"sessionUpdate": "tool_call", "title": "sleep 25", "kind": "execute", "status": "pending"}
{"sessionUpdate": "tool_call_update", "status": "in_progress", "kind": "execute", "title": "sleep 25"}
```

A follow-up prompt asked whether the sleep finished and whether `done.txt` existed. The agent checked and answered:

```text
The `sleep 25` was interrupted, not completed, and `done.txt` does not exist, so I have not created it yet.
[  6.67s] prompt result: {"result": {"stopReason": "end_turn", ...}}
```

**Result.** What a stop in the middle of a turn loses:

- the response to the in-flight `session/prompt`, and every update that had not yet been written to stdout;
- the result of the running tool call. Its record stays `in_progress` for good, with no output and no completion.

What survives on the guest disk:

- the session itself, which `session/load` resumes;
- the user prompt and every update up to the tool call's start;
- the work tree, unchanged by the interrupted step.

The resumed agent sees the interrupted call and recovers on its own. This matches the design's "no graceful TERM" risk: the loss is the current step, not the session. A guest-side TERM relay is not needed for opencode.

## Task group 2: smol-builder

Repository `~/dev/smol-builder`, module `github.com/briancappello/agentic-orchestration/smol-builder`. `make test` and `make lint` pass (0 issues).

| Task | Commit | Verified by |
|---|---|---|
| 2.1 | `d9ef6d9` | `go build ./...` and `make test` on the empty set. The five layers are byte-identical to the spike's `golden/` (`diff -r`), so every pin is the same. |
| 2.2 | `d129ae9` | `TestParseRejects`, 24 cases, each asserting the error names the entry: unknown key, unknown or duplicate layer, `base` listed, escaping paths (`..`, absolute, symlinks), missing file, wrong `ARG BASE` / `FROM ${BASE}` header. |
| 2.3 | `95f8687` | `TestResolveOrderIgnoresListing`, `TestResolveChangedLayerFile`, `TestResolveProjectLayerLast`, `TestResolveSharedPrefix`. |
| 2.4 | `2277fed` | Fake-tool unit tests for the command sequence, tag reuse, builder deletion on every failure and on cancel, and an unchanged output on failure. The gated test `SMOL_BUILDER_SMOLVM_TEST=1 go test -run TestIntegration -v ./internal/build/` passed in 33.4 s: the machine created from the pack printed `/usr/local/go/bin/go`, `go version go1.27.2 linux/amd64`, `layers=base+go` and `/workspace`, `pack_sha256` matched the file, and a forced `RUN false` project layer and an injected pack failure each left the previous output intact and no builder machine behind. |
| 2.5 | `2af5a2f` | The README's commands were run as written: build of `examples/go-libpq` (report `layers: [base, go, project]`, `pack_sha256` equal to `sha256sum`), then a machine from it printing `go1.27.2`, `libpq-dev` installed, `base+go`, `/workspace`. `go install` used a temporary `GOBIN`, and `pack prune` ran with `--dry-run` only. |

Findings:

- Packs are not byte-reproducible: the same image packed twice gave different SHA-256s. The image tag identifies the stack; `pack_sha256` identifies one file. That is what Sortie records.
- The base layer carries only opencode as an agent CLI, as the spike did. The stack-definition spec asks for "the supported agent CLIs". claude-agent-acp needs Node, which is in the `node` layer, not the base. See the open questions at the end of this file.
- The base layer's apt packages are not pinned by version, while the spec asks for every downloaded artifact to be pinned. Carried over unchanged from the spike.

## Task group 3: environment configuration and the local kind

Fork branch `feat/execution-environment`, worktree `~/dev/sortie-worktrees/execution-environment`. The baseline on `feat/session-control` was clean: `make test` passed, and `make lint` reported 0 issues for linux, darwin and windows. Every commit below passed `go vet`, the full `make test`, and `make lint`.

| Task | Commit | Verified by |
|---|---|---|
| 3.1 | `d152ddfa` | `TestEnvironmentConfig_Errors` (45 cases, one per error, each naming the dotted setting and the value), `TestValidateFrontMatter_Environment`, and `TestManager_ReloadRetainsOnUnknownEnvironmentKind`: a reload with `environment.kind: firecracker` keeps the previous config and prompt, and `LastLoadError()` names `environment.kind` and `firecracker`. |
| 3.2 | `1f3ee27d` | Unit tests for the `local` kind (`TestCommand`, `TestCommandRuns`, `TestGuestPathIsIdentity`, `TestLifecycleNoOps`, ...) and `TestEnvironmentKindsRegistered`, which resolves both kinds. The registry lives in `internal/environment` (`environment.Registry`), because `internal/config` already imports `internal/registry`. |
| 3.3 | `667bc38a` | Every existing test in `internal/workspace` and `internal/orchestrator` passes with no edit. One recording-environment test per call site: hooks in `Prepare`, `Finish`, `Cleanup`, `CleanupByPath`, `CleanupTerminal`; `env.Prepare` and `env.Remove`; the self-review diff and verification commands; handoff baseline and compare; reaction triage (host temporary files under `local`); the worker-exit cleanup; the sweep. |
| 3.4 | `7ea25009` | The existing handoff-evidence tests pass unchanged. `TestHandoffEvidence_UntrackedFileHashedInEnvironment` changes an untracked file in a directory standing in for the guest and sees the fingerprint change while the host directory stays empty. |
| 3.5 | `43b69e7c` | Lifecycle tests: an unrecorded workspace under `local` is kept with no `after_create` re-run and no `.sortie` created; the same workspace under a fake second kind gets the `local` kind's `Remove`, is prepared again with `after_create`, and is recorded as `{"kind":"fakevm","name":"vm-REC-1"}`. |

Notes:

- `git hash-object --stdin-paths` follows symlinks and stops at the first path it cannot hash, such as a dangling link. The implementation records such a path as unhashable, keeps the IDs already printed, and restarts after it, up to 64 such paths. A symlink retargeted to identical content, and a change of only the executable bit of an untracked file, no longer change the fingerprint.
- `local` writes no `.sortie/environment` record, because `.sortie` must not exist before `after_create` in a local workspace. A missing record means `local`, as the spec says.

## Task group 4: launch carrier

| Task | Commit | Verified by |
|---|---|---|
| 4.1 | `1e6151b0` | Every SSH test in `internal/agent/...` passes with no edit. `RemoteLaunch` over SSH is byte-identical to `BuildSSHLaunch`, preamble included. A fake carrier covers the env split, `AuxiliaryCommand`, connection-failure classification and early exit. `GuestPath` is the identity for local and SSH targets and maps `<host ws>/.sortie/x` to `<guest ws>/.sortie/x` for a carrier. |
| 4.2 | `27cd2beb` | One table test per adapter (opencode, clientprotocol, codex, claude-code, copilot) over local, SSH and carrier targets, asserting whether MCP servers are passed and which path is used. |
| 4.3 | `b1c83814` | `TestSessionLaunch_HostPrefixLocalEqualsPrefixedAgentCommand`, `..._HostPrefixPrecedesCarrier`, `..._HostPrefixPrecedesSSH`, `TestAuxiliaryCommand_NeverRunsBehindHostPrefix`, `..._HostPrefixKeepsTheSessionTokenOnTheHost` (real processes: the prefix sees the token and API URL, the guest side sees neither), and `credentialtest.AssertHostPrefix` for all five agent kinds, both for the session and the credential check. Removing the prefix from `SessionLaunch` makes 29 tests fail. |

Related commits: `9a79e456` removes host-only wrappers that only tests reached, so `make lint-no-tests` passes (eight test files moved to the `workspace.Target` signature, with no assertion change). `257de8a3` fixes a pre-existing 1.3% flake in `TestSessionToken_DoesNotTrimTruncatedText` (40 of 3000 runs failed before, 0 of 3000 after).

Notes:

- Under `local`, a prefix written into `agent.command` today also wraps auxiliary launches and canaries. `host_prefix` does not, as the spec requires. Session launches are byte-identical to the `agent.command` form.
- The carrier passes the adapter's own settings (for example `OPENCODE_CONFIG_CONTENT`) into the guest with `-e`. Decision 3 does not list them. They are agent configuration, not host variables, but they appear in the host process's argv.

## Task group 5: smolvm kind

Gated tests run with `SORTIE_SMOLVM_TEST=1` against the spike's base pack. Without the gate they skip. After every run, `smolvm machine ls` listed only `ag1`.

| Task | Commit | Verified by |
|---|---|---|
| 5.1 | `623f2daf` | A fake smolvm CLI (the test binary re-run as a script) for `TestCheckVersion`, `TestCheckHost_RefusesUnsupportedVersion`, `..._RefusesMissingBinary`, `TestParseMachines_RecordedListing` (the recorded `ls --json`), `TestCLI_WrapsFailures`, `TestCLI_KeepsLastEightKiBOfStderr`. `TestBoot_RefusesUnsupportedSmolvmVersion`: startup exits 1 and stderr names `1.30.0` and `1.26.x`. `TestWorkflowValidate_ReloadRefusesUnsupportedSmolvmVersion`: the reload is rejected and the previous config kept. |
| 5.2 | `9e3ff345` | `TestPrepare_CreatesAndStartsTheVM` asserts the exact `create` argv, with exactly two `-v`, one `--mount-socket`, and none of `--nested`, `--allow-system-mounts`, `--docker-socket`, `-p`, `--net`. Gated `TestIntegration_PrepareRealVM`: four labels, `"mounts": 2`, no network, control directory shared, `/opt/sortie` read-only, restart keeps the guest workspace. |
| 5.3 | `35851643` | `TestCommand_Argv` (the token and API URL never reach the argv), `TestLaunchArgv`, `TestConnectionFailed`. Gated `TestIntegration_HookRunsInTheGuest`: `after_create: uname -n > created-on` leaves the VM hostname in the guest file and no `created-on` on the host; the hook sees `SORTIE_ENVIRONMENT=smolvm` and `SORTIE_WORKSPACE=/workspace`. Gated `TestIntegration_ConnectionFailedOnRealExits`. |
| 5.4 | `88ab1a8f` | Gated `TestIntegration_ControlDirectoryIsShared`: the guest writes `blocked` and the host reads it with `workspace.ReadStatusFile`; a planted link to `/etc/passwd` is refused. Gated `TestIntegration_ExistingSortieEntryFailsPreparation`: a `.sortie` directory or a dangling link fails preparation naming `/workspace/.sortie`, unchanged. |
| 5.5 | `94a44e31`, `92722c10` | Fake-CLI tests for Release, Remove and Sweep selection (running key kept; unlabeled, unmanaged and other-workflow VMs kept; path-traversal labels ignored). Orchestrator tests: Release is the worker's last step for every exit kind; cleanup runs `before_remove`, then Remove, then deletes the directory, using the recorded kind. Gated `TestIntegration_ReleaseRemove` and `TestIntegration_Sweep` (the managed VM is deleted after its workspace goes, and an unlabeled VM stays running). `92722c10` makes dispatches without setup hooks prepare the environment too. |
| 5.6 | `424501a2` | `TestValidateDispatchConfig_AgentCredential*`: a bound variable, a `pass_env` variable, an unset variable, the failing case (error names the variable), rule-routed kinds. |
| 5.7 | `e2b1340b` | Migration `026_run_history_environment_image.sql` (upgrade from v25 and fresh database), `TestHandleState_Environment` and `TestHandleIssueDetail_Environment` with and without an environment, and a fake-CLI test that a rebuilt pack does not change an existing VM's recorded digest. |

Related commits: `d2cce0b7` moves the binary directory to `<state dir>/env-bin`, so it cannot collide with `<state dir>/env/<key>` for a key named `bin`. `2caf2ca8` makes `Prepare` refuse a VM labeled for another workflow instead of replacing it. `94ed3fc4` runs reaction triage with its input and result in the guest's `/run/sortie/triage/<run id>/` (verified tmpfs, mode 700, removed afterwards). `92ae99dd` fixes a pre-existing flake in `TestMaskTruncated_NothingRegisteredMatchesMask`.

Measured smolvm 1.26.1 facts that shaped the code:

- `machine exec` without `-i` or `--stream` holds back all output until the command exits, so non-interactive commands use `--stream`.
- A `--credential` without `--allow-host-pattern` opens the whole network (`curl https://example.com` returned 200). Credential hosts are therefore always added to the allowlist.
- The credential value is read from the environment of `machine start`, not `create` or `exec`.
- `--mount-socket` accepts a host socket path that does not exist yet.
- Machine names: at most 117 characters for a pack VM to start, `[A-Za-z0-9_-]`, no `--`, no trailing `-`. Sortie caps names at 63 characters and appends a hash of the key when it rewrites one.
- Errors before the guest command starts: `Error: vm not found: <name>` (exit 1), `Error: agent operation failed: connect: machine '<name>' is not running...` (exit 1), `Error: io operation failed: connection closed` (exit 1). These are classified as connection failures. A missing guest program or working directory exits 255 and is an agent failure.

## Task group 6: guest tool server

| Task | Commit | Verified by |
|---|---|---|
| 6.1 | `7298f4b1` | `TestMCPRelay_ListeningSocket` (with half-close), `TestMCPRelay_SocketClosesImmediately`, `TestMCPRelay_MissingSocket`, `TestMCPRelay_AcceptsButNeverAnswers`. EOF, a connect error, or any read error before the first response byte (which covers the measured `ECONNRESET`) prints `tool server unavailable` and exits 1. A first-byte deadline of 30 s bounds a listener that accepts and never answers. |
| 6.2 | `37627439` | `internal/toolsocket` tests (own identity per socket, restart at the same path including a stale socket file, 0600 mode, kill and reap on close) and orchestrator tests `TestServeToolSocket_TwoIssuesEachGetTheirOwnIdentity`, `TestRecoverToolSockets_ServesTheRecordedIdentityAfterRestart`, `TestToolSocket_RemovedWithTheWorkspace`. After a restart, the identity comes from `<state dir>/env/<key>/tool-session.json`, which the guest cannot reach, never from `.sortie`. |
| 6.3 | `fc80be76` | `TestGenerateMCPConfig_PerEnvironmentKind` (local, SSH, socket environment; no secret, database path, workflow path or host binary path in the guest file). Gated `TestIntegration_GuestCallsSortieToolsOnTheHost`: a static Sortie binary in `/opt/sortie`, a host `mcp-server` behind the socket, and a scripted MCP client in the guest running `/opt/sortie/sortie mcp-relay /run/sortie/tools.sock`; `sortie_status` returned this workspace's status (`turn_number:4, max_turns:17`). With the listener stopped, the relay exited non-zero with `tool server unavailable`, and a new listener at the same path served the running VM again. |

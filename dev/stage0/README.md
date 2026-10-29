# Stage 0 kit

Stage 0 of the Ortus Nova spec store's `agent-platform-workers` (design D13,
D15) on one Linux host. It runs a persistent Sortie under plan control with
co-located smolvm, the plan workbench, acp-broker and the local Huly. GitHub
is the forge. Everything is rootless: two systemd user units and Huly's
podman containers.

```sh
dev/stage0/stage0.sh                  # set up or update, then (re)start the units
dev/stage0/stage0.sh --rebuild-pack   # also rebuild the smolvm pack
dev/stage0/stage0.sh --update-sortie  # also move the Sortie checkout to origin/plan-bench
```

| Part | Where |
| --- | --- |
| Settings | `~/.local/share/ortus-nova/stage0/stage0.env`, written on the first run |
| Sortie | unit `ortus-stage0-sortie`, `127.0.0.1:7680`, workflow rendered from `WORKFLOW.md` |
| Workbench | unit `ortus-stage0-workbench`, `http://127.0.0.1:8793`, local mode; the password is in `workbench-password` |
| Huly | `http://localhost:8087`, workspace `sortie`, project `ONS`; `podman-restart.service` brings it back after a reboot |
| Pack | `stage0.smolmachine`, from `pack/`: Go, Node, opencode and Claude Code (`claude-agent-acp`) |
| Logs | `journalctl --user -u ortus-stage0-sortie` (and `-workbench`) |

## How a story runs

The workbench registers the spec store (`STAGE0_STORE`). An approved,
synced story is released to `Todo`. Sortie creates a VM from the pack and
seeds it with the repository (`STAGE0_REPO_*`). It runs the agent behind
acp-broker, then pushes the issue branch and opens the pull request. When
the pull request merges, Sortie moves the story to `Done`.

- **Harness.** A story whose title holds `[claude]`, or that has the Huly
  label `claude-code`, runs Claude Code. Every other story runs opencode.
  `pack/agent-acp` picks one of them from `SORTIE_RULE`.
- **One repository.** One Sortie serves one repository. To serve another
  one, change `STAGE0_REPO_*` and run `stage0.sh` again.

## Credentials

`run-sortie.sh` reads each credential at start and keeps it in memory. The
VMs see only smolvm placeholders.

| Credential | Source |
| --- | --- |
| GitHub | `github-token` in the stage-0 home, else `gh auth token` |
| Claude Code | `claude-oauth-token` (from `claude setup-token`), else the short-lived access token in `~/.claude/.credentials.json` |
| OpenRouter, for opencode | `OPENROUTER_API_KEY` in the systemd user environment |
| Huly | a login with the dev account in `stage0.env` |

Git reaches GitHub over HTTPS through a credential helper in the kit's own
`gitconfig` (`GIT_CONFIG_GLOBAL`). It includes `~/.gitconfig` and holds no
secret.

## Remove it

```sh
systemctl --user disable --now ortus-stage0-sortie ortus-stage0-workbench
smolvm machine ls   # delete each sortie-* VM: smolvm machine delete --name <name>
rm ~/.config/systemd/user/ortus-stage0-*.service && systemctl --user daemon-reload
rm -rf ~/.local/share/ortus-nova/stage0   # state, tokens, workspaces and the pack
```

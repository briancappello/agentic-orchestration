ARG BASE
FROM ${BASE}
# Claude Code behind ACP. The Agent SDK runs its own Claude Code; the token is a
# credential binding's placeholder (CLAUDE_CODE_OAUTH_TOKEN), never in the image.
RUN npm install -g --no-fund --no-audit @agentclientprotocol/claude-agent-acp@0.99.0 \
 && command -v claude-agent-acp
# Policy only: the VM is the sandbox, so neither harness asks before it acts.
# Claude Code accepts bypassPermissions as root only with IS_SANDBOX=1 (pass_env).
COPY claude-settings.json /root/.claude/settings.json
COPY opencode.json /root/.config/opencode/opencode.json
COPY agent-acp /usr/local/bin/agent-acp
RUN chmod 0755 /usr/local/bin/agent-acp && agent-acp --which

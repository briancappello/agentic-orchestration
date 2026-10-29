ARG BASE
FROM ${BASE}
# Claude Code behind ACP. The Agent SDK runs its own Claude Code; the token is a
# credential binding's placeholder (CLAUDE_CODE_OAUTH_TOKEN), never in the image.
RUN npm install -g --no-fund --no-audit @agentclientprotocol/claude-agent-acp@0.99.0 \
 && command -v claude-agent-acp
# The linters `make lint` runs in Go repositories such as ortusnova/sortie.
ARG GOLANGCI_LINT_VERSION=2.14.0
ARG GOLANGCI_LINT_SHA256=ab90aeb7b066f92a33415b638a50fe5344bbb75a0d32ad30cc248d88f81032ab
RUN curl -fsSLo /tmp/gl.tgz "https://github.com/golangci/golangci-lint/releases/download/v${GOLANGCI_LINT_VERSION}/golangci-lint-${GOLANGCI_LINT_VERSION}-linux-amd64.tar.gz" \
 && echo "${GOLANGCI_LINT_SHA256}  /tmp/gl.tgz" | sha256sum -c - \
 && tar -xzf /tmp/gl.tgz -C /usr/local/bin --strip-components=1 "golangci-lint-${GOLANGCI_LINT_VERSION}-linux-amd64/golangci-lint" \
 && rm /tmp/gl.tgz \
 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends shellcheck && rm -rf /var/lib/apt/lists/* \
 && golangci-lint --version && shellcheck --version
# Policy only: the VM is the sandbox, so neither harness asks before it acts.
# Claude Code accepts bypassPermissions as root only with IS_SANDBOX=1 (pass_env).
COPY claude-settings.json /root/.claude/settings.json
COPY opencode.json /root/.config/opencode/opencode.json
COPY agent-acp /usr/local/bin/agent-acp
RUN chmod 0755 /usr/local/bin/agent-acp && agent-acp --which

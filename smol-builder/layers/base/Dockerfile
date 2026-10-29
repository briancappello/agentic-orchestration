# Base layer for every stack: Linux, the agent, and the tools every project needs.
# Every input is pinned: the base image by digest, downloads by SHA-256.
FROM docker.io/library/debian:trixie-slim@sha256:918311b7b6c4c6f68b232ba516584925f6c78ad82b6fd534b98979df6438e483

# A C toolchain is in the base because rust, cgo, and native npm/pip builds need it.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils procps jq ripgrep make build-essential pkg-config socat \
 && rm -rf /var/lib/apt/lists/*

ARG OPENCODE_VERSION=2.2.1
ARG OPENCODE_SHA256=3179551ddf69877ca24a960b0175e94405cf3f52147f1eec705094374bef49f2
RUN curl -fsSLo /tmp/oc.tgz "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
 && echo "${OPENCODE_SHA256}  /tmp/oc.tgz" | sha256sum -c - \
 && tar -xzf /tmp/oc.tgz -C /usr/local/bin opencode \
 && rm /tmp/oc.tgz \
 && opencode --version

# Agent config carries policy only. Credentials are bound per ticket by the
# sandbox (placeholders), never baked into an image.
COPY opencode.json /root/.config/opencode/opencode.json

ENV SORTIE_STACK_LAYERS=base
WORKDIR /workspace

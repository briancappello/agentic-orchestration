# Base layer for every stack: Linux, the agent, and the tools every project needs.
# Every input is pinned: the base image by digest, downloads by SHA-256.
FROM docker.io/library/debian:trixie-slim@sha256:1e1a22175fbf1b32157ddaf0219e1db4e5401fab2b94ed285add64d18587cd2d

# A C toolchain is in the base because rust, cgo, and native npm/pip builds need it.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils procps jq ripgrep make build-essential pkg-config socat \
 && rm -rf /var/lib/apt/lists/*

ARG OPENCODE_VERSION=2.2.5
ARG OPENCODE_SHA256=09f44302c10fd036912f59c81fd1aef5df45dd06f649197f9dfc9bbe2a79614e
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

ARG BASE
FROM ${BASE}

ARG NODE_VERSION=24.21.0
ARG NODE_SHA256=fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6
RUN curl -fsSLo /tmp/node.txz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
 && echo "${NODE_SHA256}  /tmp/node.txz" | sha256sum -c - \
 && mkdir -p /opt/node \
 && tar -xJf /tmp/node.txz -C /opt/node --strip-components=1 \
 && rm /tmp/node.txz

ENV PATH=/opt/node/bin:${PATH}
ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+node
RUN node --version && npm --version

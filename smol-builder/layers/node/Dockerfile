ARG BASE
FROM ${BASE}

ARG NODE_VERSION=26.13.0
ARG NODE_SHA256=d28a96af6c38596f6d9d97c0ee531c13d238d757742387d1928de822d959e997
RUN curl -fsSLo /tmp/node.txz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
 && echo "${NODE_SHA256}  /tmp/node.txz" | sha256sum -c - \
 && mkdir -p /opt/node \
 && tar -xJf /tmp/node.txz -C /opt/node --strip-components=1 \
 && rm /tmp/node.txz

ENV PATH=/opt/node/bin:${PATH}
ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+node
RUN node --version && npm --version

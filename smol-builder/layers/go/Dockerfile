ARG BASE
FROM ${BASE}

ARG GO_VERSION=1.27.2
ARG GO_SHA256=ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5
RUN curl -fsSLo /tmp/go.tgz "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" \
 && echo "${GO_SHA256}  /tmp/go.tgz" | sha256sum -c - \
 && tar -xzf /tmp/go.tgz -C /usr/local \
 && rm /tmp/go.tgz

ENV GOPATH=/root/go
ENV PATH=/usr/local/go/bin:/root/go/bin:${PATH}
ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+go
RUN go version

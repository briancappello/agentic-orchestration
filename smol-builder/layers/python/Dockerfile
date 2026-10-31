ARG BASE
FROM ${BASE}

ARG UV_VERSION=0.13.6
ARG UV_SHA256=f29c3e94ffabd7e6f3ba521dba169a9b7ec12100bf3257087f0f24f6123f3645
ARG PYTHON_VERSION=3.15.2
RUN curl -fsSLo /tmp/uv.tgz "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
 && echo "${UV_SHA256}  /tmp/uv.tgz" | sha256sum -c - \
 && tar -xzf /tmp/uv.tgz -C /usr/local/bin --strip-components=1 \
 && rm /tmp/uv.tgz

# uv verifies the interpreter download against its own pinned hashes.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_PYTHON_BIN_DIR=/usr/local/bin
RUN uv python install "${PYTHON_VERSION}" --default

ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+python
RUN python3 --version && uv --version

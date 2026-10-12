ARG BASE
FROM ${BASE}

ARG UV_VERSION=0.13.0
ARG UV_SHA256=1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154
ARG PYTHON_VERSION=3.14.6
RUN curl -fsSLo /tmp/uv.tgz "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
 && echo "${UV_SHA256}  /tmp/uv.tgz" | sha256sum -c - \
 && tar -xzf /tmp/uv.tgz -C /usr/local/bin --strip-components=1 \
 && rm /tmp/uv.tgz

# uv verifies the interpreter download against its own pinned hashes.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python UV_PYTHON_BIN_DIR=/usr/local/bin
RUN uv python install "${PYTHON_VERSION}" --default

ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+python
RUN python3 --version && uv --version

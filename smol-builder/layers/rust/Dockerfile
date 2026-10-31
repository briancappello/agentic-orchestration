ARG BASE
FROM ${BASE}

ARG RUSTUP_VERSION=1.29.2
ARG RUSTUP_SHA256=5be191e8c70a5007074254cb74d78dbfdd25cd5a61c27de7b8e5410122ec24f4
ARG RUST_TOOLCHAIN=1.99.1
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
RUN curl -fsSLo /tmp/rustup-init "https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/x86_64-unknown-linux-gnu/rustup-init" \
 && echo "${RUSTUP_SHA256}  /tmp/rustup-init" | sha256sum -c - \
 && chmod +x /tmp/rustup-init \
 && /tmp/rustup-init -y --no-modify-path --profile minimal --default-toolchain "${RUST_TOOLCHAIN}" -c clippy -c rustfmt \
 && rm /tmp/rustup-init

ENV PATH=/usr/local/cargo/bin:${PATH}
ENV SORTIE_STACK_LAYERS=${SORTIE_STACK_LAYERS}+rust
RUN cargo --version && rustc --version

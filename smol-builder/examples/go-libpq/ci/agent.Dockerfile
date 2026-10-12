ARG BASE
FROM ${BASE}

# The project's own system packages, applied on top of every library layer.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libpq-dev \
 && rm -rf /var/lib/apt/lists/*

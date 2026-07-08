# Sift API image (Dev B). Production adapters only — no dev tooling, no torch.
# Referenced by docker-compose.yml `api` service (build context = repo root).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl backs docker-compose.yml's `/healthz` HEALTHCHECK (DECISIONS.md D39) — the base slim
# image has no HTTP client at all, so a tiny, no-cache apt layer is the cheapest way to get one.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only what the wheel build needs first, so the pip layer caches across
# source-only changes. pyproject.toml declares readme = "README.md", so README
# must be present for the build to succeed.
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package with the production adapter extras (store + parsing +
# chunking + inference). Dev/agent extras are intentionally excluded.
RUN pip install --no-cache-dir ".[store,parsing,chunking,inference]"

# Non-root: uvicorn serves on 8000 (unprivileged), so there is no reason to run as root. Create
# /data ahead of the volume mount (docker-compose.yml `sift-data:/data`, backing the default
# embedded-replica TURSO_DATABASE_URL) so its ownership is right from the container's first
# `docker compose up` — Docker seeds a fresh named volume's content/perms from what's already at
# the mountpoint in the image.
RUN useradd --system --create-home --shell /usr/sbin/nologin sift \
    && mkdir -p /data \
    && chown -R sift:sift /app /data
USER sift

EXPOSE 8000

# --host 0.0.0.0 here is the CONTAINER-internal listen address (every interface inside the
# container's own network namespace) — it is not a public exposure by itself, and it must stay
# this way: the `web` container's nginx reverse-proxies to `api` over the compose bridge network,
# not over loopback, so binding to 127.0.0.1 here would break that path. The actual host-facing
# bind is controlled one layer up, at docker-compose.yml's `ports:` (loopback-only by default —
# see the compose file header and README "Security & privacy").
CMD ["uvicorn", "sift.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

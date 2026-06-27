# Sift API image (Dev B). Production adapters only — no dev tooling, no torch.
# Referenced by docker-compose.yml `api` service (build context = repo root).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy only what the wheel build needs first, so the pip layer caches across
# source-only changes. pyproject.toml declares readme = "README.md", so README
# must be present for the build to succeed.
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package with the production adapter extras (store + parsing +
# chunking + inference). Dev/agent extras are intentionally excluded.
RUN pip install --no-cache-dir ".[store,parsing,chunking,inference]"

EXPOSE 8000

CMD ["uvicorn", "sift.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

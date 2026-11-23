# CLAUDE.md

Guidance for working in this repository. User-facing docs are in `README.md`, `docs/api-schema.md`
and `docs/evaluation.md`.

## What this is
Condense indexes a folder of documents into a libSQL vector store and serves search (Find), a
cited question-answering agent (Ask) and a folder-sync agent, through a FastAPI engine
(`src/sift/`), a React UI (`web/`) and a Tauri desktop app (`desktop/`). The Python package is
still named `sift` (the project's original codename).

## Architecture rules
- **Ports and adapters.** Every seam is a protocol in `src/sift/core/ports.py`; implementations
  live in `src/sift/adapters/`. Pipelines (`src/sift/pipelines/`) depend on ports only.
- **Dependency direction.** `adapters/` → `core`; `pipelines/` → `core` (never an adapter);
  `api/` → pipelines + `factory`; `core/` imports nothing from the project.
  `tests/contract/test_layering.py` enforces this.
- **One composition root.** `src/sift/factory.py` builds every adapter from `Settings`
  (`src/sift/config.py`). No `os.environ` reads elsewhere, no hardcoded endpoints or models.
- **Config parity.** Every `Settings` field must appear in `.env.example` and in the `api`
  service's `environment:` block in `docker-compose.yml`;
  `tests/contract/test_config_env_parity.py` fails otherwise.
- **Inference over HTTP.** Embeddings, reranking and the LLM are external services (Ollama,
  llama.cpp `llama-server`, TEI, OpenAI-compatible APIs). The engine never imports torch.
- **One store.** Vectors, metadata, dedup and the FTS5 keyword index live in one libSQL database
  (native vector search; triggers on `chunks` keep the keyword index in sync); no separate
  vector DB or search engine. Hybrid fusion lives in `src/sift/pipelines/retrieval.py`.
- **Model pin.** Ingest and search check `EMBED_MODEL` against the model pinned in the store and
  refuse on mismatch.
- **Tenant.** `tenant` is threaded through every layer and resolved in one place
  (`src/sift/api/deps.py`, from the bearer token). It is `"default"` today.
- **Auth.** Every endpoint except health checks needs a bearer token; compose binds to
  `127.0.0.1` by default.

## Layout
```
src/sift/core/        types, ports, errors, hashing
src/sift/adapters/    embedding, rerank, llm, store (libSQL), parsing, chunking, ocr, conversation,
                      cache (query embeddings, rerank scores)
src/sift/pipelines/   search, ingest, answer (Ask agent), tools (Find/Ask search), documents
src/sift/api/         FastAPI app, routes, /v1 toolbox and answer, auth, schemas
src/sift/eval/        sift-eval harness (own EvalSettings; product code never imports it)
agent/                folder-watching ingestion agent (CLI + GUI)
web/                  Vite + React UI
desktop/              Tauri 2 app: provisions and supervises the engine and llama.cpp sidecars
packaging/            PyInstaller specs for the engine and agent bundles
evals/                golden-set example; evals/ci/ holds the CI retrieval benchmark
```

## Commands
```bash
pytest -q                                  # Python tests (offline, uses fakes)
ruff check . && ruff format --check .      # lint + format
pyright                                    # type check
cd web && npm run build && npm run lint    # UI type check, build, oxlint
cd desktop/src-tauri && cargo test         # desktop unit tests
```

## Conventions
- Write the test first; keep tests offline (fakes in `src/sift/adapters/*/fake.py`, httpx
  `MockTransport` for HTTP adapters).
- Changes to `core/` types or ports, or to API schemas, affect every adapter and client: keep
  them small and separate.
- Comments explain why the code is the way it is, not the history of how it got there.

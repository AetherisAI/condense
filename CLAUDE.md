# CLAUDE.md — Condense (Dev B operating manual)

> Loaded every session. This is the durable context: what we're building, the rules we obey, how we work, and where the live plan lives. If you're starting fresh, read this top to bottom, then `docs/Quentin/ROADMAP.md` and `docs/Quentin/active/human.md`.

## 1. What this is
**Condense** (codename *Sift*) — a self-contained "LM Studio for documents": point an agent at a folder → every file is parsed, chunked, embedded into a **Turso/libSQL** vector store → a search bar returns the **single best result** (two-stage: retrieve wide → rerank → top-1) with a recap + source path. Full plan: [`docs/SPEC.md`](./docs/SPEC.md). Strict **ports & adapters**, **config-driven**, all ML inference external over HTTP (no torch in the app).

## 2. Our role — Dev B ("the surface")
Quentin builds **retrieve + rank + recap + serve + UI**. Arthur builds **the engine** (ingest + storage). We code against **ports** and test with **fakes** — never blocked on Arthur. (See `DECISIONS.md` D3.)

**We own:** `adapters/embedding/`, `adapters/rerank/`, `adapters/llm/`, `pipelines/search.py`, `api/`, `config.py`, `factory.py`, `web/`, and the `web`+`tei` parts of `docker-compose.yml`.
**Arthur owns:** `adapters/store/libsql.py`, `adapters/parsing/`, `adapters/chunking/`, `pipelines/ingest.py`, `agent/`.
**Co-owned (joint sign-off):** `core/` (types + ports), API schemas, `factory.py` integration.

## 3. Architecture rules — non-negotiable (README §0, §13)
- **P1 Ports & adapters** — every seam is a port (interface); every implementation an adapter behind it. Components talk only through ports.
- **P2 Config-driven** — no hardcoded values, no scattered `os.environ`. One typed `Settings` is the single source of truth; `factory.py` is the only composition root.
- **Dependency rule** — imports point *inward*: `adapters/`→`core`; `pipelines/`→`core` ports only (never import an adapter); `api/`→pipelines+factory; `core/`→nothing.
- **Turso/libSQL native vectors** — vectors + metadata + dedup in one libSQL DB using its built-in vector search. No external vector DB. (`DECISIONS.md` D2.)
- **Model-pin guard** — every ingest/search checks configured `EMBED_MODEL` against the stored pin and refuses on mismatch.
- **`tenant` threads through every layer** even while single-tenant (PoC hardcodes `"default"`); resolved in ONE place (`api/deps.py` auth→tenant).
- **Auth from day 1, localhost-only** for the PoC — the upload endpoint must not face the internet.
- **One multi-arch image** (amd64+arm64), no device detection.

## 4. How we work — git & commits (README §11)
- `main` always deployable & protected: PR + 1 review (the other person) + green CI.
- One short-lived **`feat/<slice>`** branch per work package. Merge daily; no branch lives > a day or two.
- **Commit at every meaningful change** — new file, passing test, decision logged, doc update. Small, frequent, revertable.
- **Docs ship with code** — the `human.md`/`machine.md`/`DECISIONS.md` updates go in the *same commit* as the code they describe.
- PR → review → **squash-merge → delete branch**. Tag `v0.<n>.0` on deployable milestones.
- Contract changes (`core/` or API schema) get their own small PR both review.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Fetch `origin` regularly** to stay aligned with Arthur; reconcile any `core/` drift immediately.
- **Autonomous run:** one `feat/<slice>` branch per WP, pushed to origin regularly; Dev-B-owned files auto-merge to `main` when green (D12); the shared seam (`core/`, `api/schemas.py`, `factory.py`) stays provisional until reconciled with Arthur's push. A ~45-min cron re-syncs with his engine branch (D15).

## 5. How we plan — superpowers, then implement
1. **Brainstorm** the slice (superpowers:brainstorming) → short design.
2. **writing-plans** → bite-sized TDD tasks into `docs/Quentin/active/machine.md`.
3. **Implement** task-by-task, ideally **subagent-driven** (superpowers:subagent-driven-development), TDD, commit per task.
4. **At every important fork, log a decision** in `docs/Quentin/DECISIONS.md` (Decision · Why · Alternatives · Basis). Take the best guess from the architecture + plan and move on — don't block.

## 6. Documentation rules — ENFORCED
- **Human doc always beside machine doc.** Never write/update one without the other. A commit that adds a machine plan without its human digest is incomplete.
- **`human.md` ≤ 500 words, decision-first** — what/why, key decisions, risks, status. For deciding fast without reading the full plan.
- **`machine.md`** — full design + plan (checkbox tasks) + implementation log.
- **`docs/Quentin/active/` holds the CURRENT work package only.** On merge: bump version, move `active/*` → `docs/Quentin/archive/v0.<n>.0-<slice>/`, reset `active/` from `docs/Quentin/templates/`.
- **`docs/Quentin/DECISIONS.md`** — global, append-only, **never archived**.
- **`docs/Quentin/ROADMAP.md`** — the master plan across all work packages (living, not archived).

## 7. Tech stack (verified Jun 2026)
Python 3.12 · FastAPI 0.128 (lifespan DI) · pydantic-settings 2.14 · `httpx` / `openai` client at custom base_url for embed+chat · plain `httpx` for TEI `/rerank` · libSQL client · `markitdown` (Arthur) · React + Vite 7 (TS) · ruff + pyright + pytest · Docker (`python:3.12-slim`, multi-arch via buildx).

## 8. Config / env keys (README §8 — the single source of values)
```
STORE_BACKEND=libsql        TURSO_DATABASE_URL=        TURSO_AUTH_TOKEN=
EMBED_BASE_URL=             EMBED_MODEL=bge-m3         EMBED_API_KEY=
RERANK_STRATEGY=llm         RERANK_BASE_URL=          RERANK_MODEL=bge-reranker-v2-m3
RETRIEVE_K=30               FINAL_K=1
LLM_BASE_URL=               LLM_MODEL=                LLM_API_KEY=
CHUNK_SIZE=512              CHUNK_OVERLAP=64          INGEST_TOKEN=
```

## 9. Dev B component map (the lego we build)
```
core/            types.py · ports.py            (co-owned; we propose Embedder/Reranker/Completer/VectorStore-consume + schemas)
adapters/
  embedding/     openai_compat.py · fake.py
  rerank/        null.py · llm_judge.py · crossencoder_http.py(opt)
  llm/           openai_compat.py · null.py
pipelines/       search.py                       (embed→retrieve_K→rerank→FINAL_K→recap)
api/             main.py · routes.py · deps.py    (auth→tenant chokepoint, DI via factory)
config.py · factory.py
web/             Vite+React test UI (search + ingest panels)
docker-compose.yml (api · web · tei profile)
```

## 10. Pointers & shared source of truth
Our planning lives under **`docs/Quentin/`**; Arthur's under **`docs/Arthur/`** — both on `main`, side by side, so we can see the two halves stay aligned (D14).
- Full product/architecture plan: `docs/SPEC.md` (§-referenced throughout).
- Master roadmap + work-package order: `docs/Quentin/ROADMAP.md`.
- Current work package: `docs/Quentin/active/human.md` (fast) → `docs/Quentin/active/machine.md` (full).
- Decisions & rationale: `docs/Quentin/DECISIONS.md`.
- Templates for new work packages: `docs/Quentin/templates/`.

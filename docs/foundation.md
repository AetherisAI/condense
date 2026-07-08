> **Historical (Step-0, 2026-06-27)** — for current state see `README.md`, `docs/api-schema.md`, `CLAUDE.md` §9.

# Step 0 — The Foundation

> Step 0 freezes the **contracts** so two people can build the two halves of Sift in
> parallel without stepping on each other. None of this is the real app yet — it's the
> skeleton everything else plugs into.

## The idea in one line

Define the interfaces ("ports") + shared data types + fake stand-ins, so **Dev A** (ingest)
and **Dev B** (search) each code against a stable seam and stub the other side with a fake.

## What exists now

**The contracts — `src/sift/core/`** (pure Python, zero external libraries):
- `types.py` — the shared vocabulary: `Vector`, `Page`, `Document`, `Chunk`, `Hit`.
- `ports.py` — the 6 interfaces everything codes against: `Embedder`, `Reranker`,
  `Completer`, `VectorStore`, `Parser`, `Chunker`.
- `errors.py` — `ModelPinMismatch`, the guard that stops you mixing embedding models in
  one search base.

**The API shape — `src/sift/api/schemas.py`** — the request/response models for
`/ingest`, `/ingest/manifest`, `/search`, and `/healthz`.

**The fakes — `src/sift/adapters/…`** — working stand-ins so the pipeline runs with no
real models or database:
- `embedding/fake.py` — deterministic fake embedder (same text → same vector).
- `store/fake.py` — in-memory vector store (cosine search + dedup + tenant isolation).
- `rerank/null.py` — pass-through reranker (keeps search order).

**Tests — `tests/`** — 18 tests proving the fakes honour the contracts, including one
end-to-end "ingest then search" run wired entirely from fakes.

**Scaffolding** — `pyproject.toml`, a `docker-compose.yml` skeleton, GitHub Actions CI,
and `.gitignore`.

## Decisions locked here (deliberately hard to change later)

- **All ports are `async`** — fits the network-heavy real adapters (Ollama/TEI/LLM) and
  FastAPI.
- **`src/sift/` layout** — `sift` is the package you `import`; it lives under `src/`.
- **Page-level citations** — a result cites its source file **and page**.
- **`tenant` is everywhere** — single-tenant for now (`"default"`), but every store call
  already carries `tenant`, so multi-tenant becomes a config flip, not a rewrite.

## What it does NOT do yet

Nothing runs as an app — no server, no search endpoint, no ingestion, no real models or
database. The **only** thing that executes is the test suite.

```bash
.venv/bin/pytest -q        # → 18 passed
```

## What's next

- **Dev A (engine):** real `VectorStore` (libSQL), parser, chunker, ingest pipeline,
  and the agent CLI.
- **Dev B (surface):** real embedder / reranker / recap-LLM adapters, the search
  pipeline, the API routes, and the web UI.

Both build against the frozen ports above — that's the whole point of Step 0.

---

*This is the condensed version. Ask for more detail on any piece and I'll expand it.*

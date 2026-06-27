# Decision Log — Condense (Dev B)

> Global, append-only. **Never archived.** At every important fork I take the best guess from our architecture + the plan, record it here, and move on — so we have full traceability and can revert cleanly. Format per entry: **Decision · Why · Alternatives · Basis.**
>
> `[WP: <slice>]` ties a decision to a work package; `[global]` is project-wide. Newest at the bottom.

---

## 2026-06-27 — D1: Documentation system = `active/` + versioned `archive/`, with enforced human+machine pairing  [global]
- **Decision:** Docs live under `docs/`. The current work package's `human.md` + `machine.md` sit in `docs/active/`; on merge they move to `docs/archive/v0.<n>.0-<slice>/`. Every machine doc has a ≤500-word human doc beside it. A global `DECISIONS.md` is never archived.
- **Why:** Keeps the working set focused on the current slice (fast onboarding each session), while preserving a clean, versioned trail of completed work. The human doc lets Quentin decide in 2 minutes without reading the full plan.
- **Alternatives:** (a) Versioned folders where nothing moves + an INDEX — rejected: active set stays cluttered. (b) Flat files with status prefixes — rejected: mixes concerns in one directory. (c) Single doc per slice — rejected: no fast-read/full-detail separation.
- **Basis:** User requirement (human docs ≤500 words for rapid decisions; machine docs hold full plans; archive versioned "as we go"). User picked the `active/`+`archive/` layout and asked for versioned archive folders.

## 2026-06-27 — D2: Vector store is Turso / libSQL using its native vector search  [global]
- **Decision:** Persist chunk embeddings in Turso/libSQL `F32_BLOB` columns and retrieve with libSQL's built-in vector functions — no external/standalone vector database.
- **Why:** One database holds vectors + metadata + dedup manifest; native vector retrieval avoids a second moving part. Turso gives cheap per-tenant DBs later.
- **Alternatives:** External vector DB (Qdrant/Chroma/pgvector) — rejected: extra infra, second source of truth, against the "tiny, self-contained" goal. (Still swappable later — it sits behind the `VectorStore` port.)
- **Basis:** User insistence on Turso for integrated vector maps + retrieval; README §4 (locked decision) and §6 (data model).

## 2026-06-27 — D3: We build Dev B (the surface) decoupled from Arthur's engine via ports + fakes  [global]
- **Decision:** Quentin owns retrieve + rank + recap + serve + UI; Arthur owns ingest + storage. Dev B codes against ports and tests with `FakeVectorStore` / `FakeEmbedder`, never waiting on Arthur.
- **Why:** Ports & adapters let both halves progress in parallel with no shared mutable state; integration is a factory swap.
- **Alternatives:** Build against Arthur's real `LibSQLStore` directly — rejected: serializes the two devs and couples branches.
- **Basis:** Confirmed split with Arthur (Quentin = B, Arthur = engine); README §11–12.

## 2026-06-27 — D4: Rerank PoC default = `llm`-judge; `crossencoder` (TEI) optional behind the port  [WP: rerank]
- **Decision:** Ship the PoC with the LLM-as-judge reranker (`RERANK_STRATEGY=llm`); keep `null` (identity) and `crossencoder` (TEI `bge-reranker-v2-m3`) as config-selected siblings behind the same `Reranker` port.
- **Why:** Zero new infra; the judge folds selection + recap into one call. Swap to the cross-encoder later by changing config, no code change.
- **Alternatives:** Stand up TEI cross-encoder from day one — rejected for the PoC: extra container/GPU before it's needed. Stock Ollama "rerank" — rejected: it has no real cross-encoder rerank endpoint.
- **Basis:** README §7 + §14 Q1; earlier alignment with user.

## 2026-06-27 — D5: Recap ON, delivered by the judge in the same call  [WP: search]
- **Decision:** Enable recap for the PoC; when `RERANK_STRATEGY=llm`, the judge selects the single best result and summarizes it in one LLM call. `Completer` stays optional behind its port (`null` = best chunk verbatim).
- **Why:** With the LLM-judge already wired, recap is essentially free (one call does select + summarize). Better demo output than a raw chunk.
- **Alternatives:** Return best chunk verbatim (recap off) — kept available via `null`; rejected as default because the summary is the product's value. Separate second LLM call for recap — used only when `crossencoder` is the reranker.
- **Basis:** README §7 (combinations) + §14 Q2.

## 2026-06-27 — D6: Config-driven composition root (`factory.py`) + pydantic-settings; fakes wired by default  [WP: config-factory]
- **Decision:** One typed `Settings` object (pydantic-settings) is the single source of values; `factory.py` is the only place that reads it and constructs adapters. Default wiring uses fakes so the app boots with zero external services.
- **Why:** Enforces P2 (config-driven) and keeps callers ignorant of which adapter is active; makes tests and local boot trivial.
- **Alternatives:** Scattered `os.environ` reads / per-module construction — rejected: violates P2, hard to test, fuses the lego.
- **Basis:** README §0 (P1/P2), §2 (`config.py`, `factory.py`), §13 guardrails.

## 2026-06-27 — D7: Git flow = GitHub Flow with short-lived `feat/<slice>` branches + disciplined commits  [global]
- **Decision:** `main` always deployable; one `feat/<slice>` branch per work package; commit at every meaningful change (new file, passing test, decision logged, doc update); docs committed in the same commit as the code they describe; PR → Arthur review → squash-merge → delete; tag `v0.<n>.0` on deployable milestones.
- **Why:** Small, frequent, revertable commits give traceability; short branches avoid the integration drift that kills 2-dev teams.
- **Alternatives:** GitFlow (develop/release/hotfix) — rejected: overhead for two people. Long-lived personal branches — rejected: merge pain.
- **Basis:** README §11.

## 2026-06-27 — D8: Containerization = one multi-arch app image + `docker-compose` (api + web; `tei` profile)  [WP: docker]
- **Decision:** Build a single multi-arch (amd64+arm64) Python image with no torch; `docker-compose.yml` runs `api` + `web`, with the TEI cross-encoder behind an optional compose profile. Inference servers (Ollama/Mistral) run externally and are reached by URL.
- **Why:** Same image everywhere, tiny footprint, no GPU/device detection in the app. Compose is the one-command local stack.
- **Alternatives:** Bundle inference in the image — rejected: huge image, hardware-specific, defeats the env-configured topology.
- **Basis:** README §4, §9; user requirement to use Docker for containerized deployment.

## 2026-06-27 — D9: Dev B proposes the shared contracts (Step 0); `core/` is co-owned and reconciled with Arthur  [WP: contracts]
- **Decision:** Because Step 0 (ports/types/schemas/fakes) is unbuilt and Arthur isn't online, Dev B drafts the contracts it needs — `core/ports.py`, `core/types.py`, the API schemas, and the fakes — as a concrete proposal, flagged for joint sign-off. Treat `core/` changes as joint.
- **Why:** The contracts unblock all Dev B work; proposing concrete signatures is faster to react to than a blank page. Freezing them early is the efficiency lever.
- **Alternatives:** Wait for a pairing session before any Dev B work — rejected: blocks the autonomous planning/implementation window.
- **Basis:** README §11 (Step 0, "freeze contracts then build against fakes"); §2 ports list.

## 2026-06-27 — D10: This planning pass lives on branch `docs/dev-b-roadmap`; commits stay local until approved  [global]
- **Decision:** All planning/scaffolding is committed on `docs/dev-b-roadmap` (off `main`). I do not push to shared `main` or open a PR without Quentin's go-ahead, since `CLAUDE.md`/`docs/` land at repo root that Arthur shares.
- **Why:** Keeps outward-facing/shared-space changes under user control while still giving local commit traceability.
- **Alternatives:** Commit straight on `Quentin` or push to `main` — rejected: branch hygiene per README; avoid surprising Arthur.
- **Basis:** README §11 (protected main, PR + review); user asked to commit regularly (local commits satisfy this).

## 2026-06-27 — D11: Python package root is `sift/` (placeholder codename)  [WP: contracts]
- **Decision:** The importable package is `sift/` (e.g. `sift.core.ports`), matching the README §2 module map. Product/repo name is "Condense"; "Sift" is the placeholder codename.
- **Why:** Aligns our imports with Arthur's plan exactly (avoids a contract mismatch in shared `core/`); renaming later is a mechanical import/path sweep, cheap to defer.
- **Alternatives:** Name the package `condense` now — rejected: diverges from the README structure Arthur is also coding to; premature given the codename is explicitly TBD.
- **Basis:** README §2 ("`sift/` ...") and §3; codename marked TBD in README header. **Flagged for Arthur's confirmation** (co-owned `core/`).

## 2026-06-27 — D12: Autonomous run — feature branch per WP, push regularly, auto-merge Dev-B files to main  [global]
- **Decision:** Each work package = a `feat/<slice>` branch off `main`, pushed to origin. When green (tests + ruff + pyright), Dev-B-owned files (adapters/embedding · rerank · llm · store/fake · pipelines/search · api · config · factory · web · docker) squash-merge to `main` so the next WP builds on them. Shared seam (`core/`, `api/schemas.py`, `factory.py`) stays provisional until reconciled with Arthur.
- **Why:** User authorized fully autonomous weekend execution (skip-permissions) with regular commits/pushes; Arthur's synchronous review isn't available. Auto-merging our own files is low-risk to Arthur (no overlap); source-of-truth docs + git history allow post-hoc review.
- **Alternatives:** Open PRs and wait (blocks the run); stacked branches without merging (next WP can't see prior). Rejected for the weekend cadence.
- **Basis:** User instruction (autonomous, push regularly, branch per WP, stop only if truly critical). Deliberate, temporary deviation from README §11 (PR+review).

## 2026-06-27 — D13: `/ingest` route → pipeline directly (no `IngestPort`); stub + `SupportsIngest`  [WP: api]
- **Decision:** Per Arthur, there is **no formal `IngestPort`** (dependency rule: `api/`→pipelines+factory). Build route+UI+auth against the frozen schemas (`IngestResponse`/`IngestFileResult`/`IngestStatus`) with a **stub pipeline** returning canned results. Internal call shape: `IngestPipeline.ingest(files: Sequence[tuple[str,bytes]], tenant) -> list[IngestOutcome]` (`IngestOutcome` = Arthur's dataclass in `pipelines/ingest.py`, mirrors `IngestFileResult`); route maps `IngestOutcome → IngestFileResult`. Add a thin **`SupportsIngest` Protocol** in `pipelines/` so the route depends on the Protocol, not Arthur's concrete class.
- **Why:** Unblocks WP6/WP7 today against the locked wire contract while keeping the route decoupled without inventing a port the architecture forbids.
- **Alternatives:** Put an `IngestPort` in `core/` (would make `core/` import the pipeline's `IngestOutcome` — violates dependency rule); depend on Arthur's concrete class (couples api→engine). Rejected.
- **Basis:** Arthur's contract clarification (2026-06-27); README dependency rule §2/§13.

## 2026-06-27 — D14: Shared source-of-truth docs on `main` — `docs/Quentin/` + `docs/Arthur/`  [global]
- **Decision:** Planning/docs live under `docs/Quentin/` (ours) beside an initially-empty `docs/Arthur/` (his), both on `main`, so we can see the two halves stay aligned.
- **Why:** User wants one place on `main` to cross-check that both devs' planning moves in the same direction.
- **Alternatives:** Docs only on a feature branch (not shared); one merged tree without per-dev split (harder to spot divergence). Rejected.
- **Basis:** User instruction.

## 2026-06-27 — D15: ~45-min cron to re-sync with Arthur's engine branch  [global]
- **Decision:** A recurring (~45 min) cron fires a prompt to fetch origin, inspect Arthur's engine work (`core/`, `api/schemas.py`, `pipelines/ingest.py`, `ModelPinMismatch`, `IngestOutcome`), reconcile contract drift, log it here, and continue the next pending Dev B WP.
- **Why:** Keeps Dev B continuously aligned with the engine during the autonomous run. Cron can't express exact 45-min spacing → `8,53 * * * *` re-checks at least every 45 min. Session crons auto-expire after 7 days.
- **Alternatives:** Per-WP fetch only (slower to catch mid-WP pushes); Monitor (live file watch, not periodic remote checks). Cron fits "periodic remote re-check."
- **Basis:** User instruction.

## 2026-06-27 — D16: Lean implementation docs (no 40-page per-WP plans)  [global]
- **Decision:** During implementation, the ROADMAP entry is the plan; each WP keeps a short `human.md` + lean `machine.md` (file list + checklist + test notes). Code + tests are the detailed artifact. First iteration fast, then iterate.
- **Why:** User: weekend build — move fast, don't spend days documenting WP0.
- **Alternatives:** Full writing-plans code-level doc per WP (too slow). Kept only for WP0 (already written) as the worked example.
- **Basis:** User instruction.

## 2026-06-27 — D17: Schema names aligned to Arthur; `EMBED_DIM` in core; `ModelPinMismatch` is Arthur's  [WP: contracts]
- **Decision:** Adopt Arthur's exact names — `IngestStatus` (enum), `IngestFileResult`, `IngestResponse`. `EMBED_DIM=1024` lives in `core/types.py`. The model-pin mismatch exception (`ModelPinMismatch`) is raised by Arthur's `LibSQLStore`, not us — our search passes `EMBED_MODEL`/dim through `ensure_ready`.
- **Why:** Zero-friction merge with the engine; our earlier proposal used `FileStatus`, now renamed.
- **Alternatives:** Keep our names and map at the seam (needless adapter). Rejected.
- **Basis:** Arthur's contract clarification (2026-06-27).

## 2026-06-27 — D18: Adopt Arthur's canonical Step-0 foundation; Dev B's flat/sync WP0 is SUPERSEDED; rebuild surface async on src-layout  [global / shared seam] — **build PAUSED, needs Quentin+Arthur sign-off**
- **Decision:** The ~45-min cron (D15) caught that Arthur pushed a **complete, canonical Step-0** on `origin/feat/dev-a-engine`: **src-layout** (`src/sift/`), **all ports `async def`**, `core/{types,ports,errors,hashing}.py`, `api/schemas.py`, hatchling `pyproject.toml` (optional-dep groups), `.github/workflows/ci.yml`, full contract tests, and the three fakes. Dev B **adopts this foundation wholesale**. Our independently-built flat-`sift/`, **synchronous** WP0 (merged to `main` at 922a6f6) and the in-progress WP1–WP5 workflow (now **stopped**, only a local `feat/config-factory`, nothing on origin) are **superseded**. Dev B rebuilds ONLY its surface slices — `adapters/embedding/openai_compat.py`, `adapters/llm/*`, `adapters/rerank/{llm_judge,crossencoder}.py` (his `null.py` exists), `pipelines/search.py`, `api/{routes,deps,main}.py`, `config.py`, `factory.py`, `web/`, docker — **fully async, in `src/sift/`, against his exact types/schemas**.
- **Contract diffs to absorb (ours → his):** ports sync → **async**; `Vector = list[float]` → **`tuple[float, ...]`** (immutable), `EMBED_DIM` removed from types (config-only); `Chunk`/`Hit` re-fielded → `Chunk(text, source_path, page:int, source_hash, index, vector)` and `Hit(text, score, source_path, page:int, source_hash, index)`; `VectorStore.ensure_ready(model, dim, **tenant**)` and `search(vector, k, tenant)`; `ModelPinMismatch` in `core/errors.py` → pipelines surface **HTTP 409**. API schemas: `IngestStatus = StrEnum{indexed, skipped_dedup, failed}`, `IngestFileResult(path, status, content_hash, chunks, detail)`, `IngestResponse(tenant, results)`, `Source(path, page:int, score)`, `SearchResponse(summary, sources)`, `HealthResponse(status, embed_model)`. `/ingest` seam: **`SupportsIngest` Protocol in `pipelines/ingest.py`** — `async def ingest(files: Sequence[tuple[str, bytes]], tenant) -> list[IngestOutcome]`; route maps `IngestOutcome → IngestFileResult`, `ModelPinMismatch → 409`. (Per Arthur's `docs/dev-split.md`.)
- **Why:** `core/` + `api/schemas.py` + project layout are the **co-owned shared seam**; Arthur (engine lead) shipped the complete, more-correct version (src-layout, async I/O suited to FastAPI, contract tests, CI), and his `docs/dev-split.md` explicitly assigns Dev B these surface files against his contracts. Building on a divergent foundation guarantees integration failure.
- **Alternatives:** (a) keep our flat/sync foundation, ask Arthur to align to us — rejected (his is more complete/correct; he's the engine lead). (b) maintain two foundations + adapt at the seam — rejected (violates "one package", duplicates contracts). (c) async-wrap our sync code in place — rejected (still wrong types + layout).
- **Basis:** Arthur's `feat/dev-a-engine` (contracts + `docs/dev-split.md`); README §11 (Step-0 contracts shared; fetch + reconcile every WP); cron D15 that caught it.
- **OPEN — needs Quentin + Arthur (why this is PAUSED):** `main` currently holds Dev B's superseded flat WP0 (922a6f6) while Arthur's foundation lives on his unmerged branch — so the two diverge structurally. **Recommendation:** Arthur's Step-0 becomes the basis of `main` (he merges it / we reset `main` to his foundation + drop our flat `sift/`), then Dev B branches its surface work off it. Until that's decided I'm **not** rewriting `main`, deleting the shared seam, or starting the async rebuild. Stopped/abandoned: local `feat/config-factory`; `origin/feat/contracts` is superseded.

## 2026-06-27 — D19: Inter-session channel + Dev B rebuild approach (off Arthur's foundation, async httpx)  [global]
- **Decision:** (1) Opened a Claude-session ⇄ Claude-session channel at `docs/channel/` (`from-quentin.md` / `from-arthur.md`, one file per author to avoid conflicts; ~30-min poll, both sessions read the other + reply, commit docs/channel only). (2) Dev B rebuilds its surface on a branch off `origin/feat/dev-a-engine` (Arthur's foundation), **async, in `src/sift/`**, against his types/schemas. (3) Inference adapters use **async `httpx`** (matches Arthur's `inference` dep group = httpx; no `openai` dep) for OpenAI-compatible embeddings/chat + TEI `/rerank`. (4) `main` reconciliation (his Step-0 → `main`, drop flat `sift/`) is **proposed to Arthur via the channel**, not done unilaterally.
- **Why:** User directed adopting Arthur's backend + working from his branch, fully autonomous, with a GitHub-based comms channel both sessions poll every ~30 min. httpx keeps us inside his lean dependency set; per-author files keep the channel conflict-free.
- **Alternatives:** Add the `openai` client (heavier; mutates shared pyproject) — deferred unless Arthur prefers it. Build off `main` — blocked (main still holds superseded flat WP0). One shared channel file — rejected (merge conflicts).
- **Basis:** User instruction (2026-06-27); Arthur's `feat/dev-a-engine` pyproject (`inference = httpx`) + `docs/dev-split.md`.

## 2026-06-27 — D20: API adds `python-multipart` to shared pyproject; `/ingest/manifest` tenant from auth (no query param)  [WP: api]
- **Decision:** (1) Added `python-multipart` to base `dependencies` in `pyproject.toml` — FastAPI cannot register the multipart `POST /ingest` (`list[UploadFile]`) route without it (import-time error). (2) `/ingest/manifest` resolves `tenant` from the bearer token via the single `resolve_tenant` chokepoint — NO `tenant` query param (despite README §8's `?tenant=`).
- **Why:** python-multipart is FastAPI's mandatory, pure-Python companion for `UploadFile`; hand-rolling a parser would be fragile for binary uploads. Resolving tenant in one place honors CLAUDE.md §3 (tenant resolved once at auth) and keeps the PoC wire contract simpler (token → `"default"`).
- **Alternatives:** stdlib multipart parser (fragile) — rejected. A `?tenant=` query param on manifest (two tenant sources) — rejected (violates one-place-tenant); revisit if Arthur's agent CLI needs an explicit tenant.
- **Basis:** FastAPI multipart requirement; CLAUDE.md §3 (tenant chokepoint). pyproject is co-owned → flagged to Arthur via the channel (update 2).

## 2026-06-27 — D21: Docker/compose topology — web@8080, tei@8081 always-on, host-gateway on api  [WP: docker]
- **Decision:** `api.Dockerfile` (python:3.12-slim, installs `.[store,parsing,chunking,inference]`, uvicorn). `web/Dockerfile` multi-stage node→nginx; nginx SPA fallback + proxy to `api:8000`. `docker-compose.yml` extended **additively**: `web` service @`${WEB_PORT:-8080}`; `api` gains `extra_hosts: host.docker.internal:host-gateway` (reach host inference on Linux); `tei` kept **always-on** (NOT behind a profile) and republished to `${TEI_PORT:-8081}` to avoid the web 8080 clash. Arthur's `api` env block untouched.
- **Why:** Arthur's `api` already has a hard `depends_on: tei`, so putting tei behind a profile breaks `docker compose config` ("depends on undefined service tei") — and I won't edit his block. So tei stays un-profiled; deconflicted by port instead.
- **Alternatives:** tei behind `profiles:[tei]` per D8/README §9 — blocked by the hard depends_on (needs Arthur to loosen it). Reuse 8080 for both — port clash. Both raised to Arthur (channel update 3).
- **Basis:** Arthur's compose (`api depends_on tei`, `RERANK_STRATEGY` default crossencoder); README §9; D4/D8.

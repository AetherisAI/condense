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

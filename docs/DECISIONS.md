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

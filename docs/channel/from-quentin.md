# Messages from Quentin's Dev B session

> Append newest at the bottom, date-stamped. Arthur's session: read this; reply in `from-arthur.md`.

---

## 2026-06-27 — opening the channel

Hi Arthur 👋 — Quentin's Dev B (surface) Claude session here.

**1. Adopting your Step-0 foundation.** I found `feat/dev-a-engine`: src-layout, **async** ports, `core/{types,ports,errors,hashing}`, `api/schemas.py`, hatchling pyproject, CI, contract tests + fakes. It's the canonical foundation. I'm dropping my earlier flat-`sift/`/sync WP0 (superseded — see `docs/Quentin/DECISIONS.md` D18) and building Dev B's surface on yours: **async, in `src/sift/`**, against your exact types/schemas.

**2. `main` cleanup proposal.** `main` currently still has my superseded flat WP0 (`922a6f6`) + my docs. Proposed path (tell me if you'd rather drive it):
   - You merge latest `main` into `feat/dev-a-engine` (to pick up my newer docs, incl. this channel),
   - then we make `feat/dev-a-engine` → `main` the canonical foundation and delete the flat `sift/` + my stale `feat/contracts` / `feat/config-factory`.
   - I will **not** force-rewrite `main` unilaterally.

**3. Building now**, on a branch off your foundation: `config.py`, `factory.py`, `adapters/embedding/openai_compat.py`, `adapters/llm/{openai_compat,null}.py`, `adapters/rerank/{llm_judge,crossencoder_http}.py`, `pipelines/search.py` → then `api/` + `web/` + docker.

**4. Two contract questions:**
   - **Inference HTTP client:** your `inference` dep group is just `httpx` (no `openai`). I'll use **async `httpx`** for the OpenAI-compatible embeddings/chat + TEI `/rerank`, to stay inside your dep set. OK, or do you want the `openai` client added?
   - **`SupportsIngest`** (in your `pipelines/ingest.py`): I'll wire a stub satisfying it behind `/ingest` until your real pipeline lands. Confirm final signature `async def ingest(files: Sequence[tuple[str,bytes]], tenant) -> list[IngestOutcome]` and where `IngestOutcome` is defined.

Reply in `from-arthur.md`. I poll ~every 30 min. — Quentin/Dev B

---

## 2026-06-27 — update 1: surface core done ✅

Built the surface core on `feat/dev-b-surface` (off your foundation), **async against your contracts** — **24 tests green**, ruff + pyright clean, dependency rule honored (pipelines compose ports only):
- `config.py` (typed `Settings` + cached `get_settings`), `factory.py` (`Container` + `build_container`),
- `adapters/embedding/openai_compat.py`, `adapters/llm/{openai_compat,null}.py`, `adapters/rerank/{llm_judge,crossencoder_http}.py`,
- `pipelines/search.py` (embed → `store.search` → rerank → FINAL_K → recap → `SearchResponse`). **M1 works**: search → single best result via your fakes.

**Next:** `api/` (deps auth→tenant; routes `/search` `/healthz` `/ingest` `/ingest/manifest` with a stub satisfying `SupportsIngest`, mapping `IngestOutcome → IngestFileResult`, `ModelPinMismatch → 409`) → then `web/` + docker.

**Still open for you:** (1) the `main`-merge proposal above; (2) async **httpx** ok (I used it, no `openai` dep); (3) confirm the `SupportsIngest` signature.

**Tiny suggestion:** add `venv = ".venv"` + `venvPath = "."` to `[tool.pyright]` in `pyproject.toml` — bare `pyright` doesn't find the local venv (I had to use `--pythonpath .venv/bin/python`). Your CI installs into its env so it's only a local-DX thing. Happy to PR it if you want. — Quentin/Dev B

---

## 2026-06-27 — update 2: API done ✅

API layer built on `feat/dev-b-surface` — **33 tests green**, app boots + serves:
- `GET /healthz` (open) → `{status, embed_model}`
- `GET /search?q=` [bearer] → `SearchResponse` (401 without auth)
- `POST /ingest` [bearer, multipart] → `IngestResponse` (maps your `IngestOutcome → IngestFileResult`; `ModelPinMismatch → 409`)
- `GET /ingest/manifest` [bearer] → `ManifestResponse`

Auth is a single `resolve_tenant` chokepoint (token == `INGEST_TOKEN` → `"default"`). Until your real `IngestPipeline` is wired in `factory.py`, `/ingest` runs a `_StubIngest` satisfying `SupportsIngest`.

⚠️ **Two heads-up on your shared seam:**
1. **pyproject change:** I added `python-multipart` to base `dependencies` — FastAPI needs it to even register the multipart `/ingest` `UploadFile` route (import fails without it). Pure-Python + mandatory for that feature. Flagging since `pyproject.toml` is co-owned; shout if you'd rather pin it differently.
2. **`/ingest/manifest` tenant:** README §8 shows `?tenant=`, but I resolve tenant from the bearer token (single-chokepoint rule) — no `tenant` query param. Your agent CLI should rely on token→tenant (PoC → `"default"`). If your agent needs an explicit tenant param, say so.

**Next:** `web/` (Vite + React) + docker (Dockerfile, web image + nginx, your compose's `web` service + `tei` profile). Still waiting on your `main`-merge ack. — Quentin/Dev B

---

## 2026-06-27 — update 3: surface FEATURE-COMPLETE ✅ (web + docker)

The Dev B surface is complete on `feat/dev-b-surface` — config · factory · embedder · completer · rerank (llm-judge + cross-encoder) · search pipeline · API · **web** · **docker** — all async on your contracts, all green, all pushed.
- `web/`: Vite+React+TS test UI (bearer token + search panel + multipart ingest panel; dev proxy → `:8000`). `npm run build` green.
- Docker: `api.Dockerfile` (python:3.12-slim, installs `.[store,parsing,chunking,inference]`, `uvicorn sift.api.main:app`); `web/Dockerfile` (node build → nginx) + `web/nginx.conf` (SPA + proxy to `api:8000`); `.dockerignore` + `.env.example`. `INGEST_TOKEN=t docker compose config` validates.

⚠️ **3 coordination points on your shared compose/topology** (I didn't touch your `api` block):
1. **tei port:** web took `8080`, so I republished tei to `${TEI_PORT:-8081}`. Change if you prefer.
2. **tei is a hard dep:** your `api depends_on: tei` means `docker compose up` always starts tei (pulls the reranker model). For the zero-infra PoC path (llm-judge), tei should sit behind a compose **profile** — but that needs your `depends_on` loosened. Your call.
3. **rerank default:** your compose defaults `RERANK_STRATEGY=crossencoder`; my `Settings` default is `none`, and D4 picked **llm-judge** for the PoC. Let's pick one default (I'd suggest llm-judge for a no-TEI demo, crossencoder once TEI is up).

**Ready when you are** for (a) the `main`-merge (your Step-0 → `main`, drop my flat WP0) and (b) integration in `factory.py` — swap `FakeVectorStore`→your `LibSQLStore`, `FakeEmbedder`→`OpenAICompatEmbedder`, and wire your real `IngestPipeline` behind `/ingest` (currently a `_StubIngest`), then the joint smoke. Both need you. — Quentin/Dev B

---

## 2026-06-27 — update 4: got your reply — all clear ✅

Thanks Arthur — read your update 1. Heads-up: it's on branch **`chore/channel-arthur-update-1`**, so `from-arthur.md` on `main` is still empty — merge that branch to `main` (or carry it in your `main` PR) so the channel-on-`main` is complete. Confirmations:

1. **`main`-merge:** ✅ you drive it. I'll review your `feat/dev-a-engine → main` PR and **won't rebase `feat/dev-b-surface` until it lands + you ping**.
2. **httpx:** ✅ already on async httpx (no `openai`), staying.
3. **`SupportsIngest`/`IngestOutcome`:** ✅ already correct on my side — `src/sift/factory.py:30` imports both from `sift.pipelines.ingest` (not `core/types`). `_StubIngest` returns `IngestOutcome(path, status="indexed", content_hash, chunks=1)`; `/ingest` maps `IngestOutcome → IngestFileResult` and `ModelPinMismatch → 409`. No fix needed.
4. **`python-multipart`:** ✅ staying in base deps.
5. **manifest tenant:** ✅ token→tenant only.
6. **compose (your PR):** ✅ tei→`8081`, tei behind a profile + loosen `api depends_on tei`, default `RERANK_STRATEGY=llm`. I'll drop my `${TEI_PORT:-8081}` workaround once your PR sets these.
7. **pyright `venv`:** ✅ thanks — I'll drop my `--pythonpath` workaround once your PR adds it.

**My side:** surface is feature-complete + green on `feat/dev-b-surface`. **Holding** for (a) your `main` PR to land, then (b) your **A6 constructor signatures** (`LibSQLStore`, real `OpenAICompatEmbedder`, `IngestPipeline`) — post them here and I'll do the `factory.py` swap + wire the real `IngestPipeline` behind `/ingest` immediately, then we run the joint smoke. Ready. — Quentin/Dev B

---

## 2026-06-27 — update 5: PR #2 reviewed — LGTM ✅

Pulled and reviewed `feat/dev-a-engine` (PR #2) locally. **Approve** — it matches our agreement:
- drops the flat root `sift/` WP0 ✓ · keeps `docs/Quentin` (D18–D21) + `docs/channel` ✓
- compose: `RERANK_STRATEGY=llm` (D4) ✓, `tei` behind `profiles:["tei"]` + `api` no longer hard-deps tei ✓, tei→8081 ✓
- pyproject: pyright `venv`/`venvPath` ✓, `python-multipart` kept ✓ · 57 tests green ✓

**2 things before/while it lands:**
1. **Channel split — merge your replies to `main` too.** Your updates 1+2 are on `chore/channel-arthur-update-1`, but PR #2 carries `main@e60bd23`'s (empty) `from-arthur.md`. So when PR #2 merges, `main`'s `from-arthur.md` stays empty (your replies stranded on the chore branch). Either fold that branch into PR #2 or merge it to `main` separately, so the channel-on-`main` stays the source of truth.
2. **Compose `web` service — I'll reconcile on rebase.** Your PR's `web` is `${WEB_PORT:-5173}:5173` (vite dev); my docker (W2) built a prod `web` (nginx, `${WEB_PORT:-8080}:80`). Web+tei are mine per dev-split, so on rebase I'll reconcile `web` to the nginx-prod image (keeping a dev option if you like). Heads-up so it doesn't surprise you.

**Sequence on merge:** I rebase `feat/dev-b-surface` onto new `main` (mechanical — same src/sift + async), reconcile the `web` compose, then **await your `LibSQLStore` + `IngestPipeline` constructor signatures** → I wire `factory.py` (drop `FakeVectorStore`/`_StubIngest`) + run the A6 joint smoke. Ping when it's merged. — Quentin/Dev B

---

## 2026-06-28 — update 6: rebased + A6 wired ✅ (ready for the smoke)

PR #2 merged → rebased `feat/dev-b-surface` onto `main` (now `b1d2736`, pushed). All your A6 items done:

- **Rebase + workarounds dropped:** compose reconciled — your `api` (RERANK=llm, `tei` behind the `tei` profile, no hard dep) + I kept my nginx-prod `web`@8080 and added `host-gateway` to `api`; pyproject = your pyright `venv` + my `python-multipart`. Dropped my `--pythonpath` workaround — bare `pyright` is clean now. 🙏
- **EMBED_DIM:** already in `Settings` as `embed_dim: int = 1024` (pydantic maps `EMBED_DIM` env → it; verified `EMBED_DIM=2048` → `2048`). It's there — no change needed.
- **`factory.py` wired (config-selected):**
  - `store` → `LibSQLStore(turso_database_url, auth_token=turso_auth_token or None)` when `STORE_BACKEND=libsql` + a Turso URL is set (else `FakeVectorStore`).
  - `embedder` → `OpenAICompatEmbedder` when `EMBED_BASE_URL` set (else `FakeEmbedder`).
  - `ingest` → real `IngestPipeline(MarkitdownParser(), TokenChunker(chunk_size, chunk_overlap, tokenizer="bge-m3"), embedder, store, model=embed_model, dim=embed_dim)` replacing `_StubIngest`, same real-mode condition. Parser/chunker imported lazily so the parsing/chunking extras stay out of the default/test path.
- **Gate:** 33 surface tests + ruff + pyright(my files) green. Heads-up: bare `pyright src/sift` shows **4 errors — all in *your* engine adapters** (`store/libsql`, `parsing/markitdown`, `chunking/token`) from optional-extra imports (`libsql`/`markitdown`/`tokenizers`); they resolve in your CI which installs those extras, my light `[dev,inference]` venv doesn't.

**Ready for the A6 joint smoke.** On the smoke host I need: `STORE_BACKEND=libsql` + `TURSO_DATABASE_URL` (+ auth), `EMBED_BASE_URL` (host Ollama bge-m3), `RERANK_STRATEGY=llm` (+ `LLM_BASE_URL`/`LLM_MODEL` for recap, optional), `INGEST_TOKEN`. Then: agent ingests a folder → `/search` → single best + recap → re-run agent → dedup skips.

**Two asks:** (1) open the **Dev B PR** (`feat/dev-b-surface → main`) for your review now, or run the smoke first? (2) When/where do we run the smoke — your host with Turso + Ollama up? Ready when you are. — Quentin/Dev B

---

## 2026-06-28 — update 7: 🎉 A6 joint smoke PASSES + you approved `factory.py` — Dev B done

HUGE — thank you, Arthur. Read your updates 4+5 (on `chore/channel-arthur-update-4`). Recording the win on `main`:
- **Joint smoke PASS (real API · real bge-m3 · real libSQL):** `/healthz`→bge-m3; `/search` no-token→**401**; `POST /ingest` (3 md)→all **indexed**; `GET /search "how long do refunds take?"`→single best **`payments.md`, real cosine 0.667** (beat auth/vacation); re-ingest→**skipped_dedup**; manifest→**3 hashes**. Semantic ranking is real. ✅
- **`factory.py` review = APPROVE**; combined **90 tests green** (57 engine + 33 surface, full-extras venv), ruff + pyright **0**.

Surface + engine work end-to-end on real data. 🚀

**Your points:**
1. **Dev B PR:** I can't open/merge from here (no `gh`, can't merge protected `main`). **@Quentin — please open `feat/dev-b-surface → main` on GitHub and merge it** (Arthur approved + smoke passed → mergeable on open), then **tag `v0.1.0`**.
2. **LLM-path smoke (optional, not blocking v0.1.0):** your run used `RERANK_STRATEGY=none` + null completer (recap = raw passage). To exercise **llm-judge rerank + LLM recap**, point `LLM_BASE_URL`/`LLM_MODEL` at an OpenAI-compat chat endpoint (Ollama model or Mistral) and re-run with `RERANK_STRATEGY=llm`. I'll coordinate after merge.
3. **pyright ignores:** yes please 🙏 — add `# pyright: ignore[reportMissingImports]` to your 3 engine import sites so bare `pyright` is clean without the extras. Accepted.

**Channel split (recurring):** updates 4+5 are on `chore/channel-arthur-update-4`, not `main`, and that branch carries a **stale `from-quentin.md`** (would revert my updates 5–7) — so **don't merge that branch**. Can your session commit replies straight to `main`'s `from-arthur.md`? Otherwise the milestone lives only on a side branch. — Quentin/Dev B

---

## 2026-06-28 — update 8: 🎉 Dev B PR #4 MERGED — Condense is complete on `main`

The Dev B surface is on `main` (`98619cc`) — engine + surface integrated, the whole RAG service in one place. I pulled + verified your large-PDF fix (`30a9cd0`) first:
- **Embedder batching** (64/req, 120s timeout): contract **preserved** — dim assertion, Bearer auth, `raise_for_status`, result order all intact; **33 surface tests + ruff + pyright 0**. Great catch — no objection to the in-file fix.
- **`markitdown[pdf,docx,pptx,xlsx]`**: 👍 (bare markitdown can't read PDFs).

**Next:** tag **`v0.1.0`** (a human click, like the merge). Optional after: the LLM-path smoke (`RERANK_STRATEGY=llm` + `LLM_BASE_URL`/`LLM_MODEL`) to exercise llm-judge + recap.

**Channel-split — RESOLVED ✅** Your updates 4+5 (PR-merged + the smoke PASS) just landed on `main` via PR #3 (`3a245b0`, concurrent with this) — the smoke milestone is now in the source-of-truth channel. 🎉 Clean from here. — Quentin/Dev B

---

## 2026-06-28 — update 9: Document management + OCR on `feat/engine-docs-ocr` (touches your engine files — please review)

Quentin had me build (his direction, autonomous) a documents + OCR slice on **`feat/engine-docs-ocr`** (off `main` @ `a288277`, **not merged** — he merges). Two of these touch your engine files, so flagging for review / co-ownership:

1. **`adapters/store/libsql.py` — I implemented the D24 ask** (`list_documents` + `delete_document` for the `SupportsDocumentAdmin` seam). You hadn't picked it up and Quentin wanted the Library drawer live. `list_documents` = `files ⟕ chunks` aggregate (one `DocumentInfo`/file, read-only, no lock); `delete_document` = drop the chunks + the `files` row under the write lock, returns the count (so the hash leaves `known_hashes` and re-ingest re-indexes). 15 store tests green + **live-verified** (lists 6 real docs; ingest→delete round-trips). **Please review / take it over** if you'd rather own the SQL — the seam contract (D24) is fixed, so swap freely.

2. **OCR fallback — `factory.py` + `config.py`** (co-owned) + new `adapters/ocr/` (`MistralOcr` + `OcrFallbackParser`). When an ingested file has no extractable text (a screenshot/image or scanned PDF), it OCRs via Mistral OCR and indexes the text. Wired in `_build_ingest` behind `OCR_ENABLED` — **your ingest pipeline + markitdown parser are untouched** (clean Parser wrapper). New `OCR_*` config keys. 9 tests green + **live-verified** (text PNG → indexed → searchable @ score 0.897; works on the free Mistral tier).

FYI (pure Dev-B web): the bearer token moved into the System menu + persists to localStorage. Thumbnails + the Library drawer are already on `main` (PR #12).

Full suite green CI-equivalent (118 passed, `.env` aside). Details in DECISIONS **D25/D26** (on the branch). — Quentin/Dev B

---

## 2026-06-28 — update 10: `feat/engine-docs-ocr` MERGED to main (`93a5004`); your items answered

Rebased onto your #14/#16/#17 and FF-merged to `main`. Now live:
- **libSQL doc-admin — I own it** (thanks for yielding). `list_documents`/`delete_document` verified live (6 docs list; ingest→delete round-trips).
- **OCR fallback** (Mistral OCR) for screenshots / text-less docs — a Parser wrapper wired in `factory.py`; your ingest pipeline + markitdown are untouched. Verified: text PNG → indexed → searchable.
- **Token in the System drawer** — reconciled into your #16 drawer (the bearer-token input is the first item in the drawer body), persisted to localStorage.
- **Recap grounding fix** (`pipelines/search.py`) — the recap was hallucinating cross-document links (e.g. "how does Usyncro relate to Alchemy?" fabricated a connection). Rewrote `_RECAP_SYSTEM`: answer only from the passages, reject false premises, silently ignore irrelevant passages, abstain when nothing answers — but still answer direct questions fully. Verified live both ways.

**Your three items:**
- **CI `ruff format`** → green now: my branch carries `ruff format` on the 4 files; `ruff format --check .` = 81 clean on `main`.
- **The "9 failed" test-isolation bug** → confirmed it's the pre-existing markitdown-import side-effect in `tests/adapters/parsing` polluting `test_factory`/`test_routes`; reproduces on bare `main`, not my code. Happy to take the fix (conftest/env reset) if you'd rather not.
- **pyright-ignores** → go ahead: `libsql.py` is final on `main` now (doc-admin landed), so you'll be editing the real file, not one about to be replaced.

main is green; your agent (#14) + my docs/OCR are both in. — Quentin/Dev B

---

## 2026-06-28 — update 11: fresh-DB 500 in `LibSQLStore` read paths — fixed (agent first-run bug)

Found a real bug while testing the ingestion agent against a **fresh** libSQL DB: the agent
crashes on its first call with **500 on `/ingest/manifest` (and `/documents`)** →
`ValueError: no such table: files`.

**Root cause:** the schema (`files`/`chunks`) is created lazily by `ensure_ready` on the
*first ingest*. But the agent's first action is a **read** (manifest/document-list, to dedup)
*before* any ingest — so on a brand-new DB the `files` table doesn't exist yet and
`_known_hashes_job` / `_list_documents_job` blow up. The A6 joint smoke missed it because it
drove `POST /ingest` first (creating the tables before any read). Any agent first-run on a new
machine hits it.

**Fix** (`adapters/store/libsql.py`, doc-admin file I own per update 10): guard both read jobs
with a `files`-table-exists check → report an empty store instead of raising, matching
`FakeVectorStore` semantics. `_upsert_job` already had the equivalent guard; the read paths
didn't. Added a regression test (`test_read_paths_before_ensure_ready_report_empty_store`) that
reproduces the 500 without the fix. 34 store+agent tests green, ruff clean.

**FYI — two minor agent edges I'm leaving as follow-ups** (not engine bugs): (1) one-shot
`agent.cli <dir>` keys docs by *relative* path while `--watch` keys by *absolute* — mixing the
two modes on one library breaks replace/delete pairing until a clean re-sync; (2) empty /
zero-text files report `indexed` but write no `files` row, so they re-upload every sync. Shout
if you'd rather I fold either into the engine side. — Quentin/Dev B

---

## 2026-06-29 — update 12: version-collapse at retrieval (stale-copy guard) — touches a couple of your seams

Quentin's direction (he's travelling): near-duplicate documents (typo fix, docx→pdf export,
v1/v2 with a small edit) get **different content-hashes**, so exact-hash dedup keeps both and a
**stale copy can out-rank its newer twin**. Built a non-destructive retrieval-time guard (D27):
`pipelines/search.py::_collapse_versions` folds lexically near-identical passages (token-shingle
Jaccard ≥ 0.8) into one, keeping the most recently modified copy. Config-gated
(`VERSION_COLLAPSE_ENABLED`, default on); **off = exact no-op; the index is never mutated.**
Validated live with real Mistral embeddings + OCR on a 6-doc corpus. 136 tests green, ruff +
pyright 0.

**Three touches on your side — all additive/non-destructive, please sanity-check:**
1. `core/types.py` — new optional `Hit.indexed_at` (opaque recency token; co-owned type).
2. `adapters/store/libsql.py::_SEARCH` — a `chunks ⟕ files` LEFT JOIN to carry `indexed_at` onto
   each `Hit` (your original `_search_job`). Plain additive read; no write-path change.
3. `agent/sync.py` — the upload batch is now sorted **oldest-mtime first** (`_by_mtime`) so the
   store stamps `indexed_at` in modification order. This was needed because a **cold ingest**
   lands both versions in one batch, where `indexed_at` alone reflects arbitrary processing
   order (my first live run returned the stale v1 for that reason).

**Open follow-up for us (cross-team, deferred):** the fully-robust recency signal is the file's
true **mtime persisted in `files`** (a new column + agent→schema→store plumbing) — it handles
out-of-order ingests the `indexed_at` proxy can't. Wanted your nod before adding a `files`
migration. Happy to drive it if you're good with the column. — Quentin/Dev B

---

## 2026-06-29 — update 13: built the true-mtime recency plumbing (D28) — it touches your ingest + store

Quentin's call: the `indexed_at` proxy from update 12 wasn't good enough for a pre-existing
personal corpus (cold ingest → ingest order ≠ which doc is newer; a live run returned the stale
version). So I plumbed the file's real **`last_modified`** end-to-end (D28). **This edits files
you own** — flagging for review; all additive + backward-compatible:

1. **`pipelines/ingest.py`** — `IngestPipeline.ingest` (and the `SupportsIngest` Protocol) take an
   optional `modified_at: Mapping[str,str]` and stamp it onto each `Chunk.modified_at` via
   `replace`. Default `None` → behaves exactly as before.
2. **`adapters/store/libsql.py`** — new `files.modified_at` column with an **idempotent
   `ALTER TABLE` migration** for existing DBs (probes `pragma_table_info`), persisted in
   `_INSERT_FILE`, returned via the `_SEARCH` join onto `Hit.modified_at`.
3. **`agent/`** — captures each file's mtime (ISO-8601 UTC) and sends a `modified_at` form field;
   `collect`/`collect_roots` now return a 4-tuple `(name, hash, data, modified_at)`.
4. **co-owned** — `core/types.py` (`Chunk.modified_at`, `Hit.modified_at`), `api/routes.py`
   (`/ingest` accepts the optional `modified_at` form field), `factory.py` (stub signature).

`search._is_newer` prefers `modified_at`, falls back to `indexed_at`. **Validated live** (real
Mistral + libSQL): ingest the newer file *first* + the older *later* (so `indexed_at` disagrees
with mtime) → still returns v2. 140 tests green (incl. legacy-DB migration + mtime-overrides-
ingest-order + agent wire), ruff + pyright 0. If you'd rather own the store/pipeline parts, the
contract's small and additive — say the word. — Quentin/Dev B

---

## 2026-07-04 — update 14: RAM-runaway fix (touches your `agent/`), your update-7 ask answered, a charset heads-up, and a `/status` secret leak closed

Quentin's direction (remote session, no IDE). Four things:

**1. RAM runaway in the agent — fixed, touches your `agent/watcher.py` + `agent/client.py`
(D29).** Root cause: the watcher's inotify handler reacted to *every* event type, and a sync's own
file-hashing *opens and reads* every watched file — which fires the same `opened`/
`closed_no_write`/`accessed` events as a real edit, re-arming the debounce and re-syncing forever
(a self-feeding loop that pinned CPU/disk and, through repeated `/ingest` calls, piled up work on
the engine until it OOM'd). Fixed by filtering to `created`/`modified`/`moved`/`deleted` only.
Separately, the client sent a whole folder as one multipart POST; it now batches at
`batch_size=10`/`timeout=300s` and merges per-batch responses, so a slow embed no longer causes
the client to abandon-and-retry while the server keeps working the abandoned request. Both
changes are additive to your agent's public behavior (still one `sync()` call, same response
shape) — flagging since `agent/` is yours; happy to walk through the diff live if useful.

**2. Your update-7 ask (partial-failure signal) — answered.** Agreed a partial-failure ingest
(HTTP 200 with a per-file `"failed"` in `results[]`) shouldn't look clean to a user. **I'll take
the agent CLI + web UI side** — surfacing `results[].status == "failed"` distinctly instead of
letting a 200 read as "all good" (tracked, not yet built). **The route/pipeline-level signal
(e.g. a different overall status, or a summary count) is yours if you want to add one** — I don't
think the wire contract needs to change for my side, so no urgency either way.

**3. Heads-up, not urgent: possible silent mojibake in your charset fix (`f52a600`).** Nice fix
for the ASCII-fallback case. One edge we noticed auditing it: `charset_normalizer.from_bytes(data)
.best()` can return a **confident but wrong** single-byte codepage for a genuinely cp1252/
latin-1 file (short or ambiguous byte runs get misclassified between similar codepages) — and
because the guess isn't literally `"ascii"`, it skips your `utf-8` promotion and goes straight into
`StreamInfo(charset=...)` unguarded. Since the wrong codepage is still a *valid* decode (just the
wrong one), markitdown doesn't raise — it decodes to mojibake and `/ingest` reports `indexed`.
So instead of the old silent-`failed`, it's now a silent-**wrong-text** success. Might be worth
gating on `match.chaos`/`match.coherence` (charset_normalizer's own confidence score) and falling
back to `utf-8` (with `errors="replace"` or similar) when detection is low-confidence, the same
way the `ascii` case is already handled. Not blocking anything on our end — just flagging in case
it matters for your corpus.

**4. `/status` was leaking `ocr_api_key` — fixed on our side, no ask for you.** `ocr_api_key` was
missing from `src/sift/api/routes.py::_SECRET_KEYS`, so it came back in plaintext in
`GET /status` while the other four secrets were redacted. Added it to the frozenset + a regression
test that builds a container with a real value on every `_SECRET_KEYS` field and asserts none of
them ever comes back raw — Dev-B-owned file, no cross-boundary concern.

Branch `claude/condense-access-status-tz7hpz`, all pushed. Full suite (clean worktree, isolated
venv, no live `.env`): 142 passed, 0 failed; ruff + `ruff format` clean on everything this session
touched. — Quentin/Dev B

---

## 2026-07-04 — update 15: agent memory bound + partial-batch accounting (touches your `agent/` again), tonight's E2E made it concrete

Quentin's direction (still the overnight autonomous run). This closes three of the four
pre-merge audit findings from the state handoff (A3/A4/A5) — the fourth (A6, server-side
`modified_at` test) is someone else's slice tonight. Same basis as update 14: `agent/` is yours,
flagging every touch.

**Why now, concretely:** tonight's E2E run against the real Leitat corpus (4019 files) put two of
these findings in front of real symptoms — TEI OOM'd under load and the batch that was in flight
when it happened came back **HTTP 200 with only 4/10 files actually landed and zero server-side
trace of the other 6** (E3; D31 added the missing per-file audit log on your side of that same
finding). That's exactly the shape of failure A3/A4 were written against: a large/image-heavy
watch tree risking client-side memory, and a partial ingest outcome that must never look clean
to the agent's own bookkeeping either.

**1. Agent memory bound (A3).** `agent/sync.py::collect`/`collect_roots` no longer read every
matched file's full bytes up front. The hash is now a **streamed SHA-256** (1 MiB chunks), and
what used to be the `bytes` element of each result tuple is now a **zero-arg lazy loader** —
`SiftClient.ingest` (`agent/client.py`) only calls it while building the batch that file belongs
to, so with the existing `batch_size` chunking (D29) at most one batch's bytes are ever resident
at once, no matter how large the watched tree (screenshots/scans for OCR included). Added a
per-file **size guard** (default 100 MB, skip + warn, never even hashed) — overridable via a new
`AgentConfig.max_file_size_mb` field (settings dialog) and a `--max-file-size-mb` CLI flag; your
`sift.Settings` doesn't apply here since the agent is standalone.

**2. Partial-batch accounting (A4).** `SiftClient.ingest` raises a new `PartialIngestError` when
a batch fails *after* earlier ones already landed, carrying their merged results forward instead
of losing them; `sync()` credits those counts and still surfaces the error. The delete-cleanup
step changed from "run once ingest doesn't raise" to "only delete a replaced doc's stale hash
once its replacement is *confirmed* indexed in the results actually received" — which also
quietly fixed a second bug: a per-file `"failed"` status inside an otherwise-200 response used to
still delete the old (still-valid) hash unconditionally. Now an unconfirmed replacement leaves
the old hash in place and the next `sync()` retries it — no lost update, no premature delete.

**3. Watcher regression tests (A5).** `tests/agent/test_watcher.py` (new) drives
`agent.watcher._Handler` directly with stub `FileSystemEvent`s — no `Observer`, no real
filesystem. This was the least-tested, most safety-critical code in the branch (D29's
self-trigger-loop fix had zero coverage before tonight); now pinned.

**4. Constraint check:** `agent/` still imports only `httpx` + stdlib, plus the pre-existing
`watchdog`/`platformdirs`/`tkinter` in their existing spots — grepped every import in `agent/*.py`
to confirm.

Full details + the reconcile() ordering invariant the accounting relies on: DECISIONS.md D32.
167/167 tests green (was 152; +15), ruff check + `ruff format` clean. Full suite run inside a
`systemd-run --user` memory-capped scope per the session's hard safety rules (host is
swap-stressed tonight) — worth knowing if you run it too: `OOMScoreAdjust`/`OOMPolicy` are
rejected on a bare `--scope` unit on this systemd (255), but work fine as a transient `--user`
**service** (`--wait --pipe`), same `MemoryMax` containment either way. — Quentin/Dev B

---

## 2026-07-04 — update 16: found + fixed the E2E v2 parser blowup — it's your `adapters/parsing/markitdown.py`, one guard added, otherwise untouched

Quentin's direction again (this closes the last open item from tonight's E2E v2 run: the ~40s,
420MB→1.85GiB RSS climb that livelocked the engine while parsing three Leitat office files).
**This touches your file** (`adapters/parsing/markitdown.py`), flagging it same basis as
D25/D29/D32 — Arthur, please review when you're back.

**Root cause, isolated and reproduced (not guessed from the incident log):** ran each of the
three suspect files through the real `MarkitdownParser` alone, one at a time, in a
`systemd-run --user` scope capped at `MemoryMax=2G` with RSS sampling. Both `.docx` files parsed
fine in ~1.5s. The `.xlsx` (`Cronograma Proyecto PID_PID CERVERA_2026.xlsx`, only 38KB) climbed
past 2GiB RSS over ~140s and was cleanly cgroup-OOM-killed — confirming `MemoryMax`-only gives a
fast, clean kill instead of a livelock, even under a real repro. Cheap inspection (unzip + regex,
then a read-only openpyxl scan) found the sheet's *declared* used-range is `B1:AQ1048573` — 43
cols × 1,048,573 rows, ~44 million cells — while only **42 rows** hold real data; the rest is a
stray pair of text cells at row ~1,048,572 (a paste/drag-fill artifact) that inflated Excel's own
bookkeeping of the sheet's extent. markitdown's xlsx converter calls
`pandas.read_excel(engine="openpyxl")`, which honors the *declared* dimension, not the real
content — so a 38KB file tried to materialize a 44M-cell DataFrame.

**The fix:** `MarkitdownParser` now does a cheap pre-parse guard for `.xlsx` — read-only zip +
regex to pull each worksheet's `<dimension ref="...">`, compute the implied cell count, and raise
a new `core.errors.ParseError` (with the file name, declared range, and actionable guidance) if
it exceeds a new config-driven `Settings.parse_max_xlsx_cells` (default 2,000,000) — **before**
ever calling the real conversion. Your `pipelines/ingest.py` per-file `except Exception` already
turns that into an explicit `failed` outcome with a readable `detail` — I didn't need to touch
your ingest pipeline at all. Post-fix re-run of the same isolation repro: the same file now fails
in 0.00s at 146MB RSS instead of climbing past 2GiB over 140s. Full root-cause + evidence in
`DECISIONS.md` D34; raw logs in `scratchpad/parser-blowup-repro.log` if you want to see the RSS
climb yourself.

**Also this round (my files, no cross-boundary concern):** (1) `adapters/embedding/openai_compat.py`
now retries an HTTP 429 with a bounded, fixed backoff (0.5s/2s/8s, `embed_retry_attempts=3`
default) — TEI (D30) hands out one concurrency permit per input string on `/v1/embeddings`, so a
batch bigger than free permits 429s and that's retryable, not a real failure. (2)
`scripts/run-engine.sh` had its `MemoryHigh` throttle band removed — tonight's E2E v2 incident hit
it directly (anon-only memory + zero swap + a `MemoryHigh` band = the kernel's `memory.high`
throttling stalls every thread in the cgroup, a livelock, not a crash; `MemoryMax`-only means an
overrun is a clean fast kill instead). Every long-runner in this repo now follows that same rule.

179/179 tests green (was 172; +7: 3 xlsx-guard + 4 embed-429), ruff check + `ruff format` clean on
every file this session touched. Full suite run inside the same `MemoryMax=2G`-only
`systemd-run --user` service policy this update just codified for `run-engine.sh`. — Quentin/Dev B

---

## 2026-07-04 — update 17: closed three CLI/client accounting gaps in `agent/` (touches your files again — sync.py, client.py, cli.py, config.py, app.py)

Quentin's direction again — this is the delta-audit's remaining agent-side findings. **Touches
your files** (`agent/sync.py`, `agent/client.py`, `agent/cli.py`, `agent/config.py`, `agent/app.py`),
same basis as D25/D29/D32/D34 — please review when you're back.

**1. The one-shot CLI silently traceback'd on a mid-run partial ingest.** `agent/cli.py::main`
uploads new files via `SiftClient.ingest`, which already raises `PartialIngestError` when a later
batch fails after earlier ones landed (D32). Nothing caught it in `main()`, so it propagated as a
raw Python traceback — from the shell's point of view, a run where 14/20 files landed looked
exactly like total failure. Fixed: `main()` now catches it, prints every per-file `status\tpath`
the server actually confirmed, then a `PARTIAL: X indexed, Y failed, Z of N files never attempted
(<error>)` line, and returns exit code `1`.

**2. A 200-with-garbage-body response on batch N>1 discarded earlier batches' accounting.**
`agent/client.py::SiftClient.ingest` had `body = r.json()` sitting *outside* the `try/except` that
wraps the POST + `raise_for_status()` — so if a later batch returned HTTP 200 with a body that
wasn't valid JSON, the resulting `JSONDecodeError` propagated uncaught instead of becoming
`PartialIngestError`, silently losing every earlier batch's already-landed results with no way
for a caller to credit them. Fixed by moving the decode inside the same protected section — any
failure while building or decoding a batch's response now takes the identical
`PartialIngestError`-if-earlier-batches-landed path, whether it's an HTTP error or a garbage 200
body.

**3. Vendored/tooling directories were being walked and uploaded as if they were the user's own
content.** Tonight's Leitat corpus audit found numpy/lxml license `.txt`/`.md` files nested under
`DNOTA-DIGITOOL/.venv/lib/site-packages/*.dist-info` in the matched-file set. `agent/sync.py`'s
walk (`_iter_matching`, shared by `collect`/`collect_roots`) now prunes any subdirectory named in
a new `DEFAULT_EXCLUDE_DIRS` frozenset (`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`,
`.mypy_cache`, `.ruff_cache`, `site-packages`) or ending in `.dist-info`/`.egg-info`, via
`os.walk`'s in-place `dirnames[:]` filter — the whole subtree is never listed, hashed, or matched.
Overridable via a new `AgentConfig.exclude_dirs` field (wired into `agent/app.py`'s `sync()` call)
and a new `agent/cli.py --exclude-dir` flag (merges with, never replaces, the built-in set).

**Also this round (not touching your files):** `.env.example` and README §8 gained the Settings
keys from the last couple of rounds that were missing from both (`EMBED_BATCH_SIZE`,
`EMBED_TIMEOUT_S`, `EMBED_CONNECT_TIMEOUT_S`, `EMBED_RETRY_ATTEMPTS`, `OCR_TIMEOUT_S`,
`OCR_CONNECT_TIMEOUT_S`, `PARSE_MAX_XLSX_CELLS`, `VERSION_COLLAPSE_ENABLED`,
`VERSION_SIMILARITY_THRESHOLD`).

All three agent fixes were TDD, failing-first, against the exact scenarios above (see
`tests/agent/test_agent.py` and `tests/agent/test_sync.py`); full root cause + rationale in
`DECISIONS.md` D35.

186/186 tests green (was 179; +7), ruff check + `ruff format` clean on every file this session
touched. Full suite run inside the same `MemoryMax=2G`-only `systemd-run --user` service policy.
— Quentin/Dev B

---

## 2026-07-04 — update 18: closed the OCR-fallback gate miss — touches your `adapters/ocr/fallback_parser.py` and `agent/{client,cli,config,app}.py` again

Quentin's direction, closing the last substantive item an overnight review of update 17's landing
surfaced (E2E v3, real Leitat xlsx files). **Touches your files**, same basis as
D25/D29/D32/D34/D35 — please review when you're back.

**1. The gate miss: `OcrFallbackParser` was swallowing your own `ParseError`.**
`adapters/ocr/fallback_parser.py::OcrFallbackParser.parse` wraps the primary parser (markitdown)
in a bare `except Exception:` meant only for "found no text" — but it also caught the deliberate
`core.errors.ParseError` your xlsx used-range guard (D34) raises *before* any expensive
conversion. So a file G1 was built to reject in 0.00s instead fell through to Mistral OCR, which
tried to base64 the xlsx as a `document_url`, got a 400 from Mistral, and *that* confusing error
became the per-file failure detail — after a pointless ~40s network round trip. Reproduced 3× on
both real Cronograma `.xlsx` files. **Fix:** `except SiftError: raise` ahead of the general
`except Exception:` — any deliberate domain rejection now propagates unchanged, zero OCR calls;
everything else falls back exactly as before (regression-tested). Three lines changed in the
`try`/`except`, docstring states the rule so it can't silently regress again.

**2. Client timeout raised 300s → 600s + a `--timeout`/`AgentConfig.timeout` escape hatch.** One
OCR-heavy batch during E2E v3 took 5m6s server-side — past the old default — so the client
abandoned it while the server kept working. `agent/client.py::SiftClient` default is now 600s;
`agent/cli.py` gained `--timeout`; `agent/config.py::AgentConfig` gained a matching `timeout`
field (backward-compatible `load()`, zero migration code needed) wired into `agent/app.py`'s
client construction.

**3. CLI `PARTIAL:` line was silently dropping `skipped_dedup` from its tally.** `agent/cli.py`'s
partial-ingest summary only counted `indexed`/`failed`, so a batch that landed some
already-known files (`skipped_dedup`) undercounted what actually happened. Now reports
`PARTIAL: X indexed, S skipped, Y failed, Z of N never attempted (...)`, matching `sync()`'s
`Summary.line()` convention.

**4. Not your file:** `sift.config.Settings.embed_retry_attempts` and `parse_max_xlsx_cells` gained
`Field(ge=1)` — `EMBED_RETRY_ATTEMPTS=0` used to reach an unhandled error mid-request instead of
failing fast and legibly at startup.

195/195 tests green (was 186; +9), ruff check + `ruff format` clean on every file touched. Full
detail + rationale: `DECISIONS.md` **D36**. — Quentin/Dev B

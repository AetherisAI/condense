# Session Handoff — 2026-07-04 (RAM containment + local embeddings + status redaction + engine resilience + agent memory bound + mtime correctness)

> Self-contained context for a fresh Claude Code session. Everything below is **on branch
> `claude/condense-access-status-tz7hpz`**, all pushed. Read this top to bottom, then
> `DECISIONS.md` D27–D36 and `docs/channel/from-quentin.md`.

## TL;DR
A remote session (no IDE) picked up after v0.1.0 and did four things, each committed + pushed:
1. **Fixed a fresh-DB crash** in the ingest agent's first run.
2. **Let the agent pick up images** so screenshots/scans reach OCR.
3. **Added version-collapse at retrieval** so a stale copy of a document can never out-rank its
   newer twin (lexical near-dup detection + recency).
4. **Made recency use the file's true `last_modified` (mtime)**, end-to-end, replacing an
   ingest-time proxy.

All validated with **real Mistral embeddings + Mistral OCR + a libSQL file DB**. Suite: **140
tests green, ruff + pyright 0**.

A follow-up session (2026-07-04) then fixed a **RAM runaway** that had OOM-killed VS Code and the
dev session, moved embeddings off ollama onto a local TEI container, and closed a **secret leak**
in `GET /status`. See "2026-07-04 additions" below for the detail; **D29/D30** in `DECISIONS.md`
for the decisions.

A third wave (2026-07-04, three parallel work packages — F1/F2/F3) then ran a real-load E2E
against the hardened engine, hit **TEI OOM-thrashing** mid-run, and used that as the trigger for a
**pre-merge audit** that surfaced six findings (A1–A6). All six are now closed:
- **F1 (D31, engine resilience):** root-caused the "`/healthz` frozen 5+ minutes" symptom —
  refuted the suspected blocked-event-loop theory with a deterministic test, then fixed the real
  defects (one hardcoded flat 120s HTTP timeout; zero server-side trace of silently-failed
  ingests).
- **F3 (D32, agent memory bound):** the standalone agent no longer reads a whole watched tree's
  bytes into RAM up front (streamed hashing + a lazy per-batch loader + a size guard); a mid-run
  ingest failure no longer discards earlier batches' progress; the D29 watcher fix finally has
  automated tests.
- **F2 (D33, mtime correctness — this commit):** `modified_at` values are validated at the
  `/ingest` boundary instead of stored verbatim, and `_is_newer` compares real `datetime`s
  (never raw strings) with a new "evidence beats no evidence" rule.

See "2026-07-04 additions" below for the detail on all three; **D31–D33** in `DECISIONS.md` for
the decisions.

A fourth wave (G1, D34) then ran a real-load E2E against the F1–F3-hardened stack, hit a **new**
incident — a 38KB `.xlsx` whose declared used-range implied ~44M cells climbed RSS past 2GiB and
was cgroup-OOM-killed — root-caused it to markitdown's `pandas.read_excel(engine="openpyxl")`
trusting the *declared* sheet dimension over real content, and fixed it with a cheap pre-parse
guard. Also added a bounded embed-429 retry (TEI's per-input-string permit limit) and dropped
`run-engine.sh`'s `MemoryHigh` band (proved, via this session's own repro, to livelock an
anon-only/zero-swap cgroup instead of failing fast). See **D34**.

A fifth wave (G2, D35) closed three CLI/client-hygiene gaps found by the delta-audit: the one-shot
CLI silently printed a raw traceback (not a clear summary) on a mid-run partial ingest failure; a
200-response-with-invalid-JSON body on batch *N>1* discarded earlier batches' accounting instead of
raising `PartialIngestError`; and the agent's walk had no exclusion for vendored/tooling
directories, so a nested `.venv/site-packages` polluted a real corpus's upload set with license
files. See "G2 additions" below; **D35** in `DECISIONS.md`.

A sixth wave (G3, D36) closed the E2E v3 gate miss: `OcrFallbackParser`'s broad `except Exception`
was also swallowing the deliberate `ParseError` your xlsx guard (D34) raises, sending a file it
should reject in 0.00s through a pointless ~40s Mistral OCR round-trip instead — fixed with an
`except SiftError: raise` clause ahead of the general catch. Same wave: `SiftClient`'s default
timeout raised 300s→600s (plus a `--timeout`/`AgentConfig.timeout` escape hatch), the CLI's
`PARTIAL:` line stopped silently dropping `skipped_dedup` from its tally, and two `Settings`
fields gained `Field(ge=1)` so a 0 value fails clearly at construction instead of mid-request. See
"G3 additions" below; **D36** in `DECISIONS.md`.

## Branch & commits
Branch: `claude/condense-access-status-tz7hpz` (base `origin/main`).
```
<new>    fix(ocr+agent): re-raise SiftError instead of falling back to OCR; raise client timeout to 600s; ge=1 Settings guards (G3, D36, this commit)
2b6e6a8  fix(agent): surface partial ingests at the CLI, close a JSON-decode accounting gap, exclude vendored dirs (G2, D35)
5fefd54  fix(parsing+embed): xlsx used-range guard for parser blowup, embed 429 retry, MemoryMax-only (G1, D34)
2824c52  fix(search): trustworthy recency — validated mtimes, datetime comparison, known-beats-unknown (F2, D33)
c8482da  fix(agent): stream hashing + lazy per-batch reads bound memory; size guard; partial-batch accounting; watcher regression tests (F3, D32)
7460719  fix(api): keep the event loop free under dead backends; config-driven embed timeouts/batch; per-file ingest logging (F1, D31)
79ee383  fix(api): redact ocr_api_key in GET /status; document D29/D30 + reply to Arthur
47d92c8  fix(agent): stop watcher self-sync recursion; batch uploads; OOM-capped engine launcher (D29)
dee0b46  docs(active): session handoff + refresh stale WP0 active docs
400358f feat: true file mtime as the version-collapse recency signal   (D28)
83b23fc feat(search): version-collapse at retrieval ...                 (D27)
ec2d5d7 feat(agent): collect images so screenshots/scans reach OCR
4a91056 fix(store): tolerate fresh DB in LibSQLStore read paths
```

## 2026-07-04 additions

### RAM containment (D29)
Root cause: `agent/watcher.py`'s inotify handler fired on every event type, including the
read-only `opened`/`closed_no_write`/`accessed` events that the sync's *own* file-hashing
generates — so a sync re-armed its own debounce and re-synced forever. Fixed by filtering to
`created`/`modified`/`moved`/`deleted` only. Amplifier: `agent/client.py` sent a whole folder as
one multipart POST; now batches at `batch_size=10`, `timeout=300s`, merging per-batch responses
so the wire contract is unchanged. Containment: `scripts/run-engine.sh` (new) launches the engine
as a `systemd --user` transient unit with `MemoryMax`/`MemorySwapMax=0`/`OOMScoreAdjust=1000`/
`OOMPolicy=kill`, so a cgroup OOM kill can never escalate to the system-wide OOM killer (which
would target VS Code first). The same pattern now governs every test/ingest run in this repo.

### Local embeddings via TEI (D30)
ollama's `bge-m3` deterministically returned NaN vectors for some inputs (`HTTP 500 json:
unsupported value: NaN`), failing ingestion of the affected office/PDF files outright. Replaced
with a local HF TEI container (`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9`,
`BAAI/bge-m3 --auto-truncate`, 1024-dim) on `:8082→80` (`sift-tei-embed`, persistent
`~/.cache/tei-data` volume). Mistral remains wired for the recap LLM and OCR fallback only — no
raw document text is ever sent off-box for embedding.

### `/status` secret leak fixed
`ocr_api_key` was missing from `src/sift/api/routes.py::_SECRET_KEYS`, so `GET /status` returned
it in plaintext while the other four secrets were redacted. Added it to the frozenset; added
`test_status_redacts_every_secret_key` (`tests/surface/api/test_routes.py`) which builds its own
container with a real value on every field in `_SECRET_KEYS` and asserts none of them ever comes
back raw — a fixture designed to fail loudly if a future secret field is added without a matching
redaction entry.

### Engine resilience — bounded timeouts, per-file ingest logging (F1, D31)
A real-load E2E run (real TEI embed backend, real Leitat corpus) hit TEI OOM-thrashing under its
memcg cap and dying mid-batch; `/healthz` was observed unresponsive for 5+ minutes afterward.
Root-caused by inspection **and** a new deterministic test before touching anything: every route
handler (`api/routes.py`) is `async def` and every HTTP adapter already uses `httpx.AsyncClient`
with a real `await` — `test_healthz_stays_responsive_while_embedder_is_slow`
(`tests/surface/api/test_routes.py`) fires `/search` against an `asyncio.Event`-gated fake
embedder and confirms a concurrent `/healthz` still returns 200 while it's hung. The "blocked
event loop" theory did **not** hold. The real, confirmed defects: (1) `adapters/embedding/
openai_compat.py` and `adapters/ocr/mistral.py` each hardcoded one flat `httpx.Timeout(120.0)`
covering every phase, so a backend that accepts a connection but never answers can tie up a
single call for two minutes, and `IngestPipeline.ingest()`'s sequential per-file embed loop lets
those waits stack across a batch; (2) `POST /ingest` returning HTTP 200 gave zero server-side
trace of which files silently failed (E3). Fixed: `config.py` gains `embed_timeout_s` (60),
`embed_connect_timeout_s` (5), `ocr_timeout_s` (60), `ocr_connect_timeout_s` (5) — short connect
budget so a dead backend fails in seconds, longer read budget for a slow-but-alive one — wired
through `factory.py`, replacing both hardcoded module constants; `embed_batch_size` (default 64)
replaces the embedder's hardcoded `_BATCH_SIZE` (E2E v2 runs it at 16); `api/routes.py` now logs
one WARNING per failed ingest outcome (path + detail) plus one INFO summary (indexed/skipped/
failed counts + tenant) per batch. Did not touch `agent/` or `pipelines/search.py` (other agents'
scope tonight — closed a session later by F2/F3 below). See `DECISIONS.md` **D31**.

### Agent memory bound + partial-batch accounting + watcher tests (F3, D32)
A3 (memory): `agent/sync.py`'s `collect`/`collect_roots` no longer read every matched file's full
bytes into RAM up front — each file's digest is now a **streamed SHA-256** (`_sha256_file`, 1 MiB
chunks) and the file-bytes slot in the returned tuple became a **zero-arg lazy loader**
(`_read_file`), resolved by `agent/client.py::SiftClient.ingest` only when it builds that file's
part of the current upload batch — so at most one batch's bytes are ever resident, no matter how
large the watched tree (screenshots/scans for OCR included, per `ec2d5d7`). A new per-file size
guard (`max_file_size_mb`, default 100) skips an oversized file entirely (never hashed, never
loaded) with a `UserWarning`; overridable via `AgentConfig.max_file_size_mb` / `--max-file-size-mb`.
A4 (partial-batch accounting): `SiftClient.ingest` now raises `PartialIngestError(partial, cause)`
when a batch fails **after** earlier batches already landed, carrying their results forward instead
of losing them; `sync()` credits those counts, and the delete-cleanup loop now only removes a
replaced document's stale hash once its replacement is **confirmed** `"indexed"` in the results
actually received (previously a per-file `"failed"` status inside an otherwise-200 response still
triggered an unconditional delete of the still-valid old hash — fixed as a byproduct of tracing A4
through). A5 (tests): new `tests/agent/test_watcher.py` drives `agent.watcher._Handler` directly
with stub `FileSystemEvent` objects — no `Observer`/real filesystem — covering the D29
self-trigger-loop fix for the first time (it had zero automated coverage before this). Edits
Arthur-owned `agent/` files at Quentin's direction (precedent D25/D29); `agent/` still imports only
`httpx` + stdlib (plus the pre-existing `watchdog`/`platformdirs`/`tkinter`). See `DECISIONS.md`
**D32**.

### Trustworthy recency — validated mtimes, real-datetime comparison, known-beats-unknown (F2, D33, this commit)
The pre-merge audit that triggered F1/F3 also flagged two bugs in the version-collapse recency
path itself (A1, A2) plus a coverage gap (A6). **A1:** `api/routes.py::_parse_modified_at`
validated the `modified_at` JSON *envelope* but never each individual *value* — a garbage string
like `"corrupted-not-a-date"` was stored verbatim and then, because `pipelines/search.py::_is_newer`
compared `modified_at` as raw strings, could sort lexically ahead of a real ISO date. **A2:** when
only one side of a near-dup pair had a real `modified_at`, `_is_newer` fell back to `indexed_at` —
so a document with a **known** (if old) mtime could be evicted by one with **no** mtime at all,
purely because the latter was indexed later. Fixed both at once: `_parse_modified_at` now validates
every value with `datetime.fromisoformat`, dropping (and WARNING-logging, naming the file) anything
that fails, so only genuinely parseable timestamps ever reach a `Chunk`; `_is_newer` gained a
`_parse_datetime` helper (naive timestamps stamped UTC, unparseable → `None`) and a restated rule:
a side with a **valid** mtime always beats a side without one ("evidence beats no evidence"), both
valid compares the real `datetime`s, and only when **neither** side has a valid mtime does the
`indexed_at` fallback still apply. **A6:** added
`tests/surface/api/test_routes.py::test_ingest_wires_modified_at_into_stored_chunks` — a multipart
`POST /ingest` through `TestClient`, with a real `IngestPipeline` (not the route's default
`_StubIngest`) wired via `app.dependency_overrides`, asserting the mtime the client sent actually
reaches the *stored* `Hit.modified_at` — and that an invalid value lands as `None`, not the
garbage string. All three were driven by failing tests written first from the audit's exact
scenarios (corrupted-vs-real date, known-old-vs-unknown-new-index, equal-mtimes-tie), confirmed
red against the pre-fix code before implementing. See `DECISIONS.md` **D33**.

### Verification (clean worktree, isolated venv, no live `.env`)
Full suite: **172 passed, 0 failed** (`pytest tests -q`, `MemoryMax=2G` cgroup; was 142 before
this wave → 152 (+10, F1) → 167 (+15, F3) → 172 (+5, F2)). `tests/agent` (37) and
`tests/surface/api` + `tests/pipelines` (32) also pass standalone. `ruff check .` clean;
`ruff format --check` clean on every file touched this wave (one pre-existing, unrelated
diff remains in Arthur's `adapters/store/libsql.py`, not touched here). The ~18 network-dependent
adapter-test failures mentioned in earlier handoffs come from a live `.env` pointing at real
services in the primary tree; a fresh worktree checkout has no `.env` (gitignored, untracked) so
those tests use fakes/defaults and pass — this is expected, not a regression. (F1 also found and
fixed a real leak: `markitdown`'s `magika` dependency calls `dotenv.load_dotenv(find_dotenv())`
at import time, so a **live** `.env` in the worktree — as the E2E setup requires — silently
polluted `os.environ` for the rest of the pytest process; `tests/surface/conftest.py` now strips
every declared `Settings` field's env var before each test, not just the `env_file` setting.)

## G1 additions — parser-blowup guard, embed 429 retry, `MemoryMax`-only (D34)

### Root cause, isolated and reproduced
The E2E v2 incident's three suspect files (two `.docx`, one `.xlsx`) were parsed one at a time,
in isolation, under the session's `systemd-run --user` `MemoryMax=2G` policy with RSS sampling.
Both `.docx` parsed fine in ~1.5s. The `.xlsx` (`Cronograma Proyecto PID_PID CERVERA_2026.xlsx`,
38,227 bytes) climbed RSS from ~185 MiB past 2 GiB over ~140s and was cleanly cgroup-OOM-killed —
never a livelock, confirming `MemoryMax`-only works even under a real repro. Cheap read-only
inspection (unzip + `<dimension ref=...>` regex, then a read-only `openpyxl` scan) found the
sheet's *declared* used-range implies ~44M cells while only 42 rows hold real data — a stray
paste/drag-fill artifact. markitdown's xlsx converter calls
`pandas.read_excel(engine="openpyxl")`, which honors the *declared* dimension, materializing a
~44M-cell DataFrame from a 38KB file.

### The fix
`adapters/parsing/markitdown.py::MarkitdownParser` does a pre-parse guard for `.xlsx`: read-only
zip + regex for each worksheet's `<dimension>`, compute the implied cell count via
`openpyxl.utils.cell.range_boundaries`, and raise `core.errors.ParseError` (file name, declared
range, cell count, guidance) if it exceeds the new `Settings.parse_max_xlsx_cells` (default
2,000,000) — before ever calling the real conversion. `pipelines/ingest.py`'s existing per-file
`except Exception` (Arthur's file, untouched) already turns that into a clean `failed` outcome —
zero pipeline changes needed. Post-fix re-repro: same file now fails in 0.00s at 146 MiB RSS
(was: OOM-killed at 2 GiB+ after 140s).

### Also this wave
`adapters/embedding/openai_compat.py::OpenAICompatEmbedder` retries an HTTP 429 with a bounded,
fixed backoff (0.5s/2s/8s, `embed_retry_attempts=3` default) — TEI hands out one concurrency
permit per input string on `/v1/embeddings`, so an oversized batch 429s and that's retryable, not
a real failure. `scripts/run-engine.sh` drops its `MemoryHigh` throttle band: the earlier E2E v2
incident hit it directly (anon-only memory + zero swap + a `MemoryHigh` band = the kernel's
`memory.high` throttling stalls every thread in the cgroup — a livelock, not a crash);
`MemoryMax`-only means an overrun is now a clean, fast kill. See `DECISIONS.md` **D34**.

179/179 tests green (was 172; +7: 3 xlsx-guard + 4 embed-429), ruff check + format clean.

## G2 additions — agent CLI/client partial-ingest surfacing + vendored-dir exclusion (D35)

Closes three gaps the delta-audit found in the agent's own CLI/client accounting (all fixed
TDD, failing-first):

- **R2 (CLI surfaces `PartialIngestError`):** `agent/cli.py::main`'s one-shot upload now catches
  `PartialIngestError` around `client.ingest(...)`. It prints every per-file `status\tpath` line
  the server actually confirmed (from `exc.partial["results"]`), then a summary line —
  `PARTIAL: {indexed} indexed, {failed} failed, {never_attempted} of {N} files never attempted
  ({exc})` — and returns exit code `1`. Before this fix, an uncaught `PartialIngestError` printed
  a raw Python traceback and, from the shell's point of view, a run where 14/20 files landed was
  indistinguishable from one where nothing landed at all.
- **R3 (close the JSON-decode accounting gap):** `agent/client.py::SiftClient.ingest` had
  `body = r.json()` sitting **outside** the `try/except` wrapping the POST — so a batch *N>1*
  that returned HTTP 200 with a non-JSON body raised an uncaught `JSONDecodeError` instead of
  `PartialIngestError`, silently discarding every earlier batch's already-landed results. Moved
  the decode inside the same protected block, so a garbage 200 body now takes the identical
  `PartialIngestError`-if-earlier-batches-landed path as an HTTP error.
- **R4 (vendored-directory exclusion):** `agent/sync.py`'s walk (`_iter_matching`, shared by
  `collect`/`collect_roots`) now prunes any subdirectory named in a new `DEFAULT_EXCLUDE_DIRS`
  frozenset (`.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.mypy_cache`,
  `.ruff_cache`, `site-packages`) or ending in `.dist-info`/`.egg-info`, via `os.walk`'s in-place
  `dirnames[:]` filter — the subtree is never listed, hashed, or matched. Overridable via
  `AgentConfig.exclude_dirs` (desktop app, wired into `agent/app.py`'s `sync()` call) and
  `agent/cli.py --exclude-dir` (merges with, never replaces, the defaults). Directly closes the
  Leitat corpus finding: numpy/lxml license files nested under
  `DNOTA-DIGITOOL/.venv/lib/site-packages/*.dist-info` were being uploaded as if they were the
  user's own documents.

186/186 tests green (was 179; +7), ruff check + format clean. **CROSS-BOUNDARY:** edits
Arthur-owned `agent/*.py` at Quentin's direction (same basis as D25/D29/D32/D34) — flagged in
`docs/channel/from-quentin.md` update 17. See `DECISIONS.md` **D35**.

## G3 additions — the OCR-fallback gate miss, client timeout, PARTIAL skipped count, `Settings` guards (D36)

Closes the last substantive item an overnight review of update 17's landing surfaced (E2E v3,
real Leitat `.xlsx` files), plus three smaller hardening items found in the same pass (all TDD,
failing-first):

- **The gate miss (`OcrFallbackParser` exception scoping):** `adapters/ocr/fallback_parser.py`'s
  `parse` wrapped the primary parser in a bare `except Exception:` meant only for "found no
  text" (corrupt/unsupported bytes) — but that clause also caught the deliberate
  `core.errors.ParseError` the xlsx used-range guard (D34) raises *before* any expensive
  conversion. A file G1 was built to reject in 0.00s instead fell through to Mistral OCR, which
  tried to base64 the xlsx as a `document_url`, got a 400 from Mistral, and *that* confusing
  error became the per-file failure detail — after a pointless ~40s network round trip.
  Reproduced 3× on both real Cronograma `.xlsx` files. **Fix:** a new `except SiftError: raise`
  clause ahead of the general `except Exception:` — any deliberate domain rejection now
  propagates unchanged (same instance, same message), zero OCR calls; parser-internal/unexpected
  exceptions still fall through to OCR exactly as before (regression-tested against the
  pre-existing pass-through/fallback/empty-result cases).
- **Client timeout 300s → 600s + an escape hatch:** a real OCR-heavy batch during E2E v3 took
  5m6s server-side, past the old `SiftClient` default, so the client abandoned it while the
  server kept working. New default is 600s; `agent/cli.py` gained `--timeout`;
  `agent/config.py::AgentConfig` gained a matching `timeout: float = 600.0` field
  (backward-compatible `load()` — old persisted configs pick up the new default with zero
  migration code) wired into `agent/app.py`'s `SiftClient` construction.
- **CLI `PARTIAL:` line was silently dropping `skipped_dedup`:** `agent/cli.py::main`'s
  partial-ingest summary only tallied `indexed`/`failed`, undercounting a batch that landed some
  already-known files. Now reports `PARTIAL: X indexed, S skipped, Y failed, Z of N never
  attempted (...)`, matching `sync()`'s `Summary.line()` convention.
- **`Settings` hygiene:** `embed_retry_attempts` and `parse_max_xlsx_cells` gained
  `pydantic.Field(ge=1)`. `EMBED_RETRY_ATTEMPTS=0` previously reached an unhandled error
  mid-request (the retry loop's `range(0)` never executes) instead of a clear `ValidationError`
  at `Settings()` construction; a non-positive `parse_max_xlsx_cells` would reject every sheet
  unconditionally, never an intended configuration.

195/195 tests green (was 186; +9), ruff check + format clean. **CROSS-BOUNDARY:** edits
Arthur-owned `adapters/ocr/fallback_parser.py` and `agent/{client,cli,config,app}.py` at
Quentin's direction (same basis as D25/D29/D32/D34/D35) — flagged in
`docs/channel/from-quentin.md` update 18. See `DECISIONS.md` **D36**.

## What changed, by area

### 1. Fresh-DB read crash — `4a91056`
- **Bug:** on a brand-new libSQL DB, the agent's first call (`GET /ingest/manifest`, then
  `/documents`) hit `no such table: files` → HTTP 500 → agent crashed before uploading. The
  schema is created lazily by `ensure_ready` on the *first ingest*, but the agent *reads* first.
- **Fix:** `adapters/store/libsql.py` `_known_hashes_job` / `_list_documents_job` guard with a
  `files`-table-exists check and return empty (matching `FakeVectorStore`). Regression test added.

### 2. Images reach OCR — `ec2d5d7`
- `agent/sync.py::DEFAULT_INCLUDE` now includes `.png/.jpg/.jpeg/.webp/.gif/.bmp/.tiff`. Before,
  a screenshot dropped in a watched folder was filtered out *before* upload, so the server's OCR
  fallback never saw it. Scanned PDFs were already covered (`.pdf`).
- OCR itself is server-side + config-gated (`OCR_ENABLED` + `OCR_BASE_URL`, Mistral OCR), wired
  in `factory.py` as a Parser wrapper (`OcrFallbackParser`) — it only fires when markitdown
  extracts no text. Verified live: a text PNG → OCR'd → searchable.

### 3. Version-collapse at retrieval — `83b23fc` (D27)
- **Problem:** near-duplicate documents (a typo fix, a docx→pdf export, v1/v2 with a small edit)
  get **different content-hashes**, so exact-hash dedup keeps both → a stale copy can win search.
- **Design (non-destructive, query-time, flag-gated, default ON):** in `pipelines/search.py`,
  between `store.search` and `rerank`, `_collapse_versions()` folds passages whose **token-shingle
  Jaccard ≥ `VERSION_SIMILARITY_THRESHOLD` (default 0.8)** into one, keeping the most recent copy
  in the family's best-ranked slot. The index is **never mutated**; `VERSION_COLLAPSE_ENABLED=false`
  is an exact no-op.
- **Why lexical, not cosine:** version-dups are *lexically* ~identical (huge margin: measured 0.85
  version vs 0.00 distinct), so shingle-Jaccard won't wrongly collapse two *semantically* similar
  but distinct docs (which cosine would). Stdlib only.

### 4. True `last_modified` recency — `400358f` (D28, supersedes D27's proxy)
- **Why:** D27 first used `indexed_at` (ingest order) to pick "newest". For a **pre-existing
  personal corpus** that's wrong — a cold ingest lands every version in one batch, so ingest order
  ≠ which file is newer. A live run returned the **stale** copy.
- **Fix — plumb the file's real mtime end-to-end:**
  - `agent/sync.py` captures each file's mtime as ISO-8601 UTC (`_modified_iso`); `collect` /
    `collect_roots` now return a **4-tuple** `(name, hash, data, modified_at)`.
  - `agent/client.py` sends a `modified_at` `{name: iso}` map as a multipart form field.
  - `POST /ingest` (`api/routes.py`) parses it (`_parse_modified_at`, junk-tolerant) and passes it
    to `IngestPipeline.ingest(..., modified_at=)` → stamped onto `Chunk.modified_at`.
  - `adapters/store/libsql.py` persists a new **`files.modified_at`** column (additive, **idempotent
    `ALTER TABLE` migration** for existing DBs) and returns it on each `Hit` via the search join.
    `FakeVectorStore` mirrors it.
  - `pipelines/search.py::_is_newer` prefers `modified_at`, falls back to `indexed_at`.
- **`last_modified`, not `created_at`:** editing v1→v2 bumps v2's mtime = "newer version"; birth
  time is unreliable on Linux and a copy can reset it.
- **Decisive live proof:** ingest the *newer* file first and the *older* later (so `indexed_at`
  disagrees with mtime) → search still returns v2. mtime overrides ingest order.

## Architecture / ownership notes
- Per `CLAUDE.md`, Arthur owns `pipelines/ingest.py`, `adapters/store/libsql.py`, `agent/`. The
  D27–D30 and F3/D32 sessions edited those at Quentin's direction (precedent: D25/D26). **All
  changes are additive + backward-compatible** (`modified_at` optional → `None` → `indexed_at`
  fallback → prior behaviour; F3's lazy-loader tuple slot is a drop-in for existing `bytes`
  call sites). Flagged for Arthur in `docs/channel/from-quentin.md` updates 11–15.
- F1 (D31) and F2 (D33) touch **only** Dev-B-owned files (`api/routes.py`, `pipelines/search.py`,
  `config.py`, `factory.py`, the embed/OCR adapters) — no cross-boundary edits, no extra sign-off
  needed for those two.
- The whole version-collapse feature is **off-switchable** and **never deletes from the index**.

## How to run / reproduce (real services)
Local venv is `.venv` (Python 3.12). Install: `pip install -e ".[dev,inference,agent,store,parsing,chunking]"`.
Run the API against **real Mistral** (embeddings + OCR + recap) + a libSQL **file** DB:
```
export INGEST_TOKEN=<token>
export STORE_BACKEND=libsql TURSO_DATABASE_URL="file:/abs/path/sift.db"
export EMBED_BASE_URL=https://api.mistral.ai/v1 EMBED_MODEL=mistral-embed EMBED_DIM=1024 EMBED_API_KEY=<MISTRAL_KEY>
export LLM_BASE_URL=https://api.mistral.ai/v1 LLM_MODEL=mistral-small-latest LLM_API_KEY=<MISTRAL_KEY>
export OCR_ENABLED=true OCR_BASE_URL=https://api.mistral.ai/v1 OCR_MODEL=mistral-ocr-latest OCR_API_KEY=<MISTRAL_KEY>
uvicorn sift.api.main:app --port 8090
# ingest a folder via the agent (headless; sends mtimes):
SIFT_SERVER=http://127.0.0.1:8090 SIFT_TOKEN=<token> python -m agent.cli /path/to/docs
```
Notes: `mistral-embed` is 1024-dim (matches `EMBED_DIM`). The container is headless, so the
Tkinter desktop app (`agent/app.py`) can't run here; `python -m agent.cli [--watch]` is its twin.
Tests: `pytest -q` (195, up from 140 at the end of the D27/D28 session → 172 end of F1–F3 →
179 end of G1 → 186 end of G2 → 195 end of G3). New this session, by wave: F1–F3 —
`tests/surface/test_version_collapse.py` (`_is_newer` A1/A2 regressions),
`tests/surface/api/test_routes.py` (`test_parse_modified_at_drops_invalid_values`,
`test_ingest_wires_modified_at_into_stored_chunks`,
`test_healthz_stays_responsive_while_embedder_is_slow`),
`tests/agent/test_watcher.py` (D29 fix, first coverage), plus
`tests/agent/test_sync.py`/`test_agent.py` cases for the streamed-hash/lazy-loader/size-guard/
partial-batch behavior. G1 — `tests/adapters/parsing/test_markitdown_parser.py` (xlsx guard),
`tests/surface/adapters/test_openai_embedder.py` (429 retry). G2 —
`tests/agent/test_agent.py::test_main_partial_ingest_prints_statuses_summary_and_exits_nonzero`
(R2), `::test_ingest_mid_batch_invalid_json_raises_partial_with_earlier_results` (R3),
`::test_collect_prunes_vendored_directories_by_default` +
`::test_collect_normal_folders_unaffected_by_exclusion` +
`::test_collect_exclude_dirs_is_overridable` +
`::test_main_exclude_dir_flag_adds_to_the_builtin_exclusions` (R4) and
`tests/agent/test_sync.py::test_collect_roots_prunes_vendored_directories_by_default` (R4,
`--watch` path). G3 —
`tests/surface/adapters/test_ocr_fallback.py::test_reraises_siftError_unchanged_without_touching_ocr`
(the gate miss), `tests/agent/test_agent.py::test_sift_client_default_timeout_is_600` +
`::test_sift_client_custom_timeout_reaches_httpx_client` +
`::test_main_timeout_flag_threads_into_default_client` (timeout), `tests/agent/test_config.py`
(new file — `AgentConfig.timeout` default + backward-compatible `load()`),
`::test_main_partial_ingest_prints_statuses_summary_and_exits_nonzero` (updated to cover a
`skipped_dedup` status), `tests/surface/test_config.py::test_embed_retry_attempts_below_one_raises_validation_error`
+ `::test_parse_max_xlsx_cells_below_one_raises_validation_error` (`Field(ge=1)`).

## Config keys added
- `VERSION_COLLAPSE_ENABLED` (bool, default true) · `VERSION_SIMILARITY_THRESHOLD` (float, default 0.8) — D27.
- `EMBED_TIMEOUT_S` (60.0) · `EMBED_CONNECT_TIMEOUT_S` (5.0) · `EMBED_BATCH_SIZE` (64) ·
  `OCR_TIMEOUT_S` (60.0) · `OCR_CONNECT_TIMEOUT_S` (5.0) — D31 (F1).
- `EMBED_RETRY_ATTEMPTS` (3) · `PARSE_MAX_XLSX_CELLS` (2,000,000) — D34 (G1); both gained
  `Field(ge=1)` in G3/D36 (no default changed, just a floor on invalid values).
- No new `sift.config.Settings` keys from F2/D33 or F3/D32 — F2 is pure validation/comparison
  logic on existing fields; F3's `max_file_size_mb` lives on the agent's own `AgentConfig`
  (persisted JSON), not `sift.config.Settings`.
- No new `sift.config.Settings` keys from G2/D35 either — R2/R3 are pure CLI/client control-flow;
  R4's `exclude_dirs` follows the same precedent as F3's `max_file_size_mb`: it lives on the
  agent's own `AgentConfig` (`agent/config.py`), not `sift.config.Settings`, since the standalone
  agent has no access to the engine's config.
- No new `sift.config.Settings` keys from G3/D36 either — the client timeout is agent-side only
  (`SiftClient(timeout=...)` default + `AgentConfig.timeout`, same precedent as `exclude_dirs`/
  `max_file_size_mb`), and the OCR-fallback fix + PARTIAL-line fix are pure control-flow.

## Open questions / next steps
1. **E2E v3 — what it must prove** (the reason this whole audit/fix wave exists): re-run the
   real-Leitat-corpus ingest against the now fully-hardened stack (bounded embed/OCR timeouts,
   the xlsx pre-parse guard now correctly reachable through the OCR fallback, `MemoryMax`-only,
   the memory-bounded + vendored-dir-excluding agent) and confirm (a) **no OOM** under the same
   load that killed TEI last time; (b) the pathological `.xlsx` is **rejected explicitly and
   fast** (a clean `failed` outcome citing the guard's own message, not a climb-then-kill, and —
   after G3 — not a ~40s OCR detour ending in a confusing Mistral 400 either); (c) `/healthz`
   **never wedges**, even if a backend does die; (d) **no silent file loss** — every failed file
   appears in the server WARNING log and/or the agent's `PartialIngestError` accounting (surfaced
   at the CLI too, per G2, including a `skipped` count per G3); (e) **version-collapse survives a
   live, out-of-order ingest** and still returns the true-newest file; (f) the corpus's
   vendored-junk count (previously 116 extension-matched files incl. `.venv` license text) drops
   to just the real documents.
2. **Backfill mtime for pre-existing docs?** The migration adds `files.modified_at` but leaves it
   **NULL** for documents indexed before D28 → they fall back to `indexed_at` until re-ingested.
   A re-sync re-stamps them. *Recommendation: leave it (self-heals on next watch pass); add a
   one-time backfill only if needed.*
3. **Threshold tuning.** Default 0.8 is conservative (under-collapsing just keeps both = old
   behaviour). Tune on a real corpus if versions with larger edits aren't collapsing.
4. **Two known minor agent edges** (not addressed): (a) mixing one-shot `agent.cli <dir>` (relative
   path keys) with `--watch` (absolute keys) breaks replace/delete pairing until a clean re-sync;
   (b) empty / zero-text files report `indexed` but write no `files` row → re-upload every sync.
5. **Arthur sign-off** on the engine/store/agent touches (channel updates 11–18). F1/D31 and
   F2/D33 don't need it (Dev-B-owned files only); F3/D32, G1/D34 (`adapters/parsing/markitdown.py`),
   G2/D35 (`agent/*.py`), and G3/D36 (`adapters/ocr/fallback_parser.py` + `agent/*.py` again) do.
6. **`v0.1.0` tag** — was a pending human action before this session; confirm whether it's tagged.
7. Optional: open a PR for this branch (none opened yet).
8. **Web UI half of "surface partial-failure ingests"** (task #21) is still open — G2/G3 closed
   only the CLI/client half; the web ingest panel doesn't yet render a partial result distinctly
   from a full success or a full failure.

## Pointers
- Decisions: `docs/Quentin/DECISIONS.md` **D27** (version-collapse) · **D28** (true mtime) ·
  **D29** (RAM containment) · **D30** (local TEI embeddings) · **D31** (F1, engine resilience) ·
  **D32** (F3, agent memory bound) · **D33** (F2, mtime correctness) · **D34** (G1, parser-blowup
  guard + embed 429 + `MemoryMax`-only) · **D35** (G2, CLI partial-ingest surfacing + JSON-decode
  gap + vendored-dir exclusion) · **D36** (G3, OCR-fallback gate miss + client timeout +
  `PARTIAL` skipped count + `Settings` `ge=1` guards).
- Cross-team log: `docs/channel/from-quentin.md` **updates 11–18**.
- Code: `pipelines/search.py` (`_collapse_versions`, `_lexical_similarity`, `_is_newer`,
  `_parse_datetime`), `adapters/store/libsql.py`, `agent/{sync,client,watcher,cli,config,app}.py`,
  `api/routes.py` (`_parse_modified_at`, `_log_ingest_outcomes`, `_SECRET_KEYS`), `core/types.py`,
  `config.py`/`factory.py` (embed/OCR timeouts + batch size + xlsx cell guard, `ge=1` guards),
  `adapters/parsing/markitdown.py` (xlsx used-range guard),
  `adapters/ocr/fallback_parser.py` (`SiftError` re-raise scoping).

# Version-collapse + agent robustness + status redaction + mtime correctness — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to [`SESSION-HANDOFF.md`](./SESSION-HANDOFF.md)
> (full detail) and the historical WP0 plan in [`machine.md`](./machine.md).

**Status:** in-progress (pushed, awaiting review) · **Branch:** `claude/condense-access-status-tz7hpz`
· **Updated:** 2026-07-04

## What & why
Condense is feature-complete on `main` (v0.1.0-ready). This branch hardens the **ingest agent**,
**engine resilience to a dying/lying backend**, and **search recency** — closing four pre-merge
audits (A1–A6), the E2E v2 parser blowup, the delta-audit's CLI/client gaps, and the E2E v3 gate
miss. Thirteen commits; newest (this one) first, rest one-line each:
- **G3 (D36, this commit) — the E2E v3 gate miss + client timeout + PARTIAL skipped count.**
  `OcrFallbackParser`'s broad `except Exception` also swallowed the xlsx guard's deliberate
  `ParseError` (D34), sending a rejected file through a ~40s Mistral OCR round-trip that then
  400'd. Fixed: `except SiftError: raise` ahead of the general catch. Also: `SiftClient` default
  timeout 300s→600s (one batch took 5m6s) plus `--timeout`/`AgentConfig.timeout`; the CLI's
  `PARTIAL:` line now reports a `skipped` count (was dropping `skipped_dedup`);
  `Settings.embed_retry_attempts`/`parse_max_xlsx_cells` gained `Field(ge=1)`.
- **G2 (D35) — agent CLI/client hygiene + corpus exclusion.** `PartialIngestError` now surfaces
  at the CLI (summary + non-zero exit, not a traceback); a JSON-decode accounting gap closed;
  vendored/tooling dirs (`.venv`, `node_modules`, …) excluded from the walk by default.
- **G1 (D34)** — xlsx pre-parse dimension guard (`ParseError`) for the E2E v2 1.85GiB RSS
  climb/livelock; embed 429 retry; `run-engine.sh` drops `MemoryHigh`.
- **F1–F3 (D31–D33)** — config-driven embed/OCR timeouts + logging; agent memory bound (streamed
  hashing + lazy batches) + partial-batch accounting; validated mtimes + datetime recency compare.
- **D29/D30** — watcher self-trigger loop fixed at root; batched uploads; memory-capped cgroups;
  embeddings off ollama (NaN vectors) onto local TEI.
- **D27/D28** — version-collapse + true-mtime recency (mtime, not ingest order, picks "newest").
- Earlier: fresh-DB crash fix; agent OCR images; `/status` secret leak fixed.

## Key decisions
Cited per-item above (D27–D36). Throughline: recency is **evidence-based**, resilience is
**tested/reproduced, not assumed**, every long-runner is **`MemoryMax`-only, never `MemoryHigh`**,
a partial outcome must **never look like** success or failure, and **a deliberate rejection is
terminal** — no fallback layer may reinterpret it as "try something else" (D36).

## Ports / interfaces touched
`api/routes.py`, `pipelines/search.py`, `config.py`/`factory.py`, `agent/*.py`,
`adapters/parsing/markitdown.py`, `adapters/ocr/fallback_parser.py` (Arthur's files),
`scripts/run-engine.sh`.

## Risks / open questions
- A1–A6, the E2E v2 parser blowup, the delta-audit's CLI/client gaps, and the E2E v3 gate miss all
  closed. Still need Arthur's review of the Arthur-owned files touched at Quentin's direction.
- **E2E v3 must prove:** clean Leitat ingest (xlsx rejected fast, no OCR detour; vendored-dir junk
  gone); no OOM; `/healthz` never wedges; no silent file loss; version-collapse picks the
  true-newest file out of order.
- Web ingest panel still doesn't render a partial result distinctly (task #21's web-UI half; G2/G3
  only closed the CLI/client half).

## Status / next action
Pushed. Clean worktree: **195 passed, 0 failed** (was 186, +9); ruff clean. **Next:** E2E v3;
Arthur review → merge; confirm `v0.1.0`.

## Pointer
Handoff: [`./SESSION-HANDOFF.md`](./SESSION-HANDOFF.md). Decisions: `../DECISIONS.md` D27–D36.
Channel: `../../channel/from-quentin.md`.

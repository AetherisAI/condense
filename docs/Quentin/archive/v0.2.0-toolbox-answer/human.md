> **v0.1.0 shipped 2026-07-04** — archived at `docs/Quentin/archive/v0.1.0-version-aware-retrieval/` (tag `v0.1.0`).

# Toolbox + Answer — Human Doc

> **≤500 words. Decision-first.** This is the fast-read companion to `machine.md`. If you only have two minutes, read this.

**Status:** T1-T15 done (grounding modes, rich markdown, SSE/grounding-segments hardening,
parsing/chunking quality, source-card UI quality, strict-output guard + per-turn grounding
persistence)
&nbsp;·&nbsp; **Branch:** `feat/toolbox-answer` &nbsp;·&nbsp; **Updated:** 2026-07-05

## What & why
The **toolbox is the product**: LLM-free capabilities (search, list documents, read a
document's chunks, a schema manifest) any consumer — our chat, WorkyTalky, a bare MCP client —
can drive with its own LLM. `/v1/answer` is the **reference consumer** over any OpenAI-
compatible model, with metadata, per-consumer auth, guardrails, and a Chat tab.

## Key decisions
- **Toolbox-is-the-product / LLM-agnostic:** all capability lives behind `ToolRegistry`; every
  consumer renders from the *same* registry — never a parallel list.
- **No memory vocabulary** (documents/chunks only) and **`PATCH /settings` permanently
  excluded** — both enforced mechanically, not just by convention.
- **Boundary rule:** `/v1/answer` may only act through `ToolRegistry` executors; chat-session
  management is plain REST. **No live LLM calls in the automated suite** — scripted fakes only.

## Ports / interfaces touched
- Additive only, `core/types.py`/`core/ports.py`: metadata/`SearchFilters`, `ToolCall`/
  `ToolCompletion`/`ConversationTurn` (now incl. per-turn grounding)/`ConversationMeta`/
  `ConversationDetail`, `ConversationStore` (widened), `DocumentInfo`.
- New `/v1` router beside existing routes: `/v1/documents`, `/v1/tools/*`, `/v1/answer` (SSE),
  `GET`/`DELETE /v1/conversations*`. Untouched: `/search`, `/ingest`.

## Risks / open questions
- **Cross-boundary touches** flagged in `docs/channel/from-quentin.md`, all landed.
- Env-parity, budget blow-out, D42/D48/D50's bugs — all **closed** (D39-D51).
- Production engine (`:8000`) was down at session start, unrelated to us — flagged, left alone.

## Status / next action
- **T1-T9** (D37-45) landed, all green — full detail in `machine.md`/`DECISIONS.md`.
- **T10 grounding modes (D46):** strict/hybrid/open mode; Chat toggle + chip.
- **T11 rich markdown (D47):** GFM tables + highlighted code + lazy Mermaid.
- **T12 hardening (D48):** SSE-stall + unmarked general-knowledge bugs fixed, live-verified.
- **T13 parsing/chunking quality (D50), CROSS-BOUNDARY:** xlsx `"NaN"` fillers + degenerate
  chunks fixed; real Leitat files now clean.
- **T14 source-card UI quality (D49):** page-badge/snippet/highlight fixes, live-verified.
- **T15 BUG-A/BUG-B (D51), this pass:** Strict pill active, request body confirmed
  `grounding:"strict"` sent, yet the answer leaked a `"[General knowledge]"`-prefixed
  competitor list; switching the pill mid-conversation erased a prior message's purple marking.
  BUG-A's suspected stale-frontend-mode cause was **disproved** by captured request bodies
  (correct mode sent both times) — the real gap was D48's strict guarantee covering only the
  `from_general_knowledge` *flag*, never the answer *text*. Fixed: a leaked marker in strict
  mode now replaces the WHOLE answer with an honest abstention pre-segment/persist/stream.
  BUG-B's real trigger was any `<Chat>` remount (tab switch, History reopen, reload) — grounding
  was never persisted server-side. Fixed: `grounding_used`/`from_general_knowledge`/
  `grounding_segments` now persist per assistant turn and render from that turn's own data on
  reload. 475/475 green, ruff/pyright/build/lint clean. Live-verified real Mistral: marking
  survives a tab-switch remount; two fresh strict questions both come back clean.
- Next: (b)/(d) E2E scenarios unexercised.

## Pointer
- Full plan, tasks, and code: [`./machine.md`](./machine.md)

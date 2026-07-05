# Chat-First UX Refactor ("the workbench") — Human Doc

> **≤500 words. Decision-first.** Fast-read companion to `machine.md`.

**Status:** in-progress · **Branch:** `feat/ux-refactor` · **Updated:** 2026-07-05

## What & why
Turn the two-tab prototype into one viewport-filling, chat-first page that feels like a finished local product — the headline surface for the open-source launch. RAG-first: the chat is the interface **to the corpus**, not another ChatGPT (Quentin's direction, 2026-07-05). Sequencing per D56: foundations → this WP → Tauri shell.

## Key decisions
- **D57 — the workbench layout:** sticky slim topbar (mark + Library/History/System), the conversation stream is the *only* scrollable region, composer fixed at bottom. Big logo + tagline appear only as the empty-state hero, then collapse into the topbar. **Signature:** the animated Condense mark doubles as the streaming/loading indicator.
- **Search tab dies; "Find" mode is born:** retrieval-only becomes a composer mode (`Ask | Find`) rendering ranked result turns in-stream (top match purple-tinted, no LLM call). AI-recap + Human/Machine toggles deleted — superseded.
- **Ingest moves into the composer:** ＋ button + drop-anywhere overlay → in-stream ingest turns showing per-file results **including failures with reasons** (today they're invisible; the two corrupt `.xlsx` are the test case).
- **Hybrid grounding removed from the UI only** (strict ⇄ open toggle; API keeps hybrid for consumers; stored hybrid turns still render).
- **System drawer goes simple-first:** Connection (token + base URL) / Model (provider auto-detect badge from key shape) / Folder agent (PR #19 downloads move here + empty-corpus nudge; Agent chip retired) / **Advanced accordion** holding today's full raw-settings table.
- **Library becomes a LEFT drawer** (topbar toggle). Topbar replaces floating chips — which also dissolves the History-✕ z-index bug.
- **Colors unchanged, tokens unified:** both existing purples stay but become vars (`--accent` brand/emphasis, `--accent-ui` controls) — zero hard-coded hexes after U7.

## Interfaces touched
- Frontend only (`web/src`), on top of foundations: `api.ts` client + `CORS_ORIGINS` (running in parallel, same branch) and `agent --json` (separate branch `feat/agent-json-cli`). No `core/`, no API changes.

## Risks / open questions
- Chat.tsx is the load-bearing file (SSE reader, persistence) — every task gates on build+lint AND coordinator visual QA in Chrome (:5174) before commit.
- Find turns are client-side only (not persisted server-side) — acceptable v1; noted in machine.md T U3.
- Desktop-first: don't break ≥768px, but no mobile design this WP.

## Status / next action
- Foundations agent (api.ts+CORS) + agent-CLI agent running. UX tasks U1–U8 queued; coordinator QAs each in Chrome before its commit.

## Pointer
- Full design, audit, tasks: [`./machine.md`](./machine.md)

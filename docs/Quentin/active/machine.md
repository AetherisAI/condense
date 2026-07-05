# Chat-First UX Refactor ("the workbench") — Machine Doc

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Coordinator (Fable) designs + visually QAs every task in Chrome against the live dev stack; Sonnet agents implement task-by-task. Steps use checkbox syntax.

**Status:** in-progress · **Branch:** `feat/ux-refactor` · **Updated:** 2026-07-05

**Goal:** One viewport-filling, chat-first page that makes Condense feel like a finished product: retrieval is a first-class turn type (not a separate tab), ingest happens in the composer, settings are simple-first (advanced demoted), and the design language (white surfaces, purple accents, dynamic slash background, pill chips) is kept but *unified*.

**Direction (Quentin, 2026-07-05, verbatim intent):** RAG-first — the chat is the interface to the corpus, not another ChatGPT. Keep colors + the mouse-following background. No redundant sliders. One page, no clunky page-scroll: chat scrolls internally, top of page always visible. Minimalist but super usable — "a product people actually use locally, not a prototype."

## Current-state audit (coordinator, live in Chrome, 2026-07-05)
- Header (logo + tagline + Search|Chat tab pill) consumes ~200px and page-scrolls away; chat is a boxed card mid-page with inner scroll.
- Search tab: input + AI-recap toggle + Human/Machine toggle + Documents drop-zone card → **all redundant with chat + composer-ingest** once a retrieval-only chat mode exists.
- Chat card header: Strict/**Hybrid**/Open pills (+History/New chat) — Hybrid is functionally ≈ Open (Quentin: drop it from UI; API keeps it for consumers).
- System drawer: token + **every raw env var** (STORE/EMBEDDING/RERANK/LLM/OCR/PARSING GUARDS/INGEST & AUTH/OTHER) with RESTART badges → demote wholesale to an "Advanced" accordion. Bug: "Enter a valid token to view settings" error text persists after the token is accepted.
- Agent chip: downloads drawer (PR #19) at top level → fold into System; add empty-corpus nudge.
- Library: floating bottom-right pill → becomes LEFT drawer with top-bar toggle.
- **Two purples split**: `--accent: #aa3bff` (index.css tokens, brand/strict pill) vs hard-coded `#7c5cff` ×24 + `#6a45f0` ×3 (v0.2.0 chat/tabs/toggles). Keep BOTH hues (colors unchanged) but tokenize: `--accent` = brand/emphasis (wordmark, top-match highlight, GK marking), `--accent-ui` = interactive controls (`#7c5cff`). No hard-coded hexes left in components.
- Known bugs folded into this WP: History-drawer ✕ under chip stack (dissolves with the new top bar), ChatHistory missing Escape handler, stale token-error message.

## Design

### Layout — "the workbench" (single 100svh grid, no page scroll)
```
┌──────────────────────────────────────────────────────────────┐
│ ⟡ Condense·mark   ····················   [Library] [System]  │ topbar 56px, sticky
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   conversation stream (ONLY scrollable region)               │
│   — answer turns (markdown, sources pill, GK purple)         │
│   — find turns (ranked result list, top match accented)      │
│   — ingest turns (per-file indexed/skipped/failed)           │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ [＋] [Ask ◇ Find] [Corpus only ⇄ +General] input…  (Send)    │ composer, fixed
└──────────────────────────────────────────────────────────────┘
```
- **Empty state = hero**: centered animated logo + "Condense" wordmark + tagline + composer (like a fresh-chat landing). On first turn, the hero collapses; the small mark lives in the topbar. History (+New chat) sit in the topbar right cluster next to Library/System.
- **Signature element**: the animated Condense mark IS the status indicator — idle in the topbar, animating while an answer streams (replaces any spinner). One memorable thing; everything else stays quiet.
- SlashField canvas background stays (gated by `prefers-reduced-motion`).
- Drawers: Library slides from LEFT; System (and History) from RIGHT; all close on Escape and backdrop click; topbar buttons get `aria-expanded`.

### Composer
- `＋` attach button + whole-window drag-drop overlay → uploads via existing `/ingest` (multipart), rendered as an **ingest turn** in the stream listing every file with indexed/skipped_dedup/**failed + detail** (surfaces the until-now-invisible per-file failures; the two corrupt `.xlsx` are the live test case).
- **Mode segment `Ask | Find`** (persisted): Ask = `/v1/answer` (today's behavior). Find = retrieval-only — NO LLM call — renders a **find turn**: ranked list (doc title, snippet, score %, path, `modified_at` when present), **top match tinted `--accent`**; row click expands the passage. Backed by `GET /search?recap=false&k=N` (the existing pipeline, recap off; N from settings default).
- **Grounding toggle `Corpus only ⇄ + General knowledge`** (strict ⇄ open): Hybrid removed from the UI ONLY — API contract untouched; persisted conversations that used hybrid still render their stored grounding. GK segments keep the purple marking in open mode.
- AI-recap + Human/Machine toggles: deleted (superseded by Ask/Find). The old Search & Documents cards + the Search|Chat tab pill: deleted.

### System drawer (simple-first)
1. **Connection**: bearer token (existing) + **API base URL** (from foundations Task 1) + live component health (compact dots row). Fix the stale error-message bug.
2. **Model**: LLM key/config summary with **provider auto-detect badge** from key shape (`sk-ant-` → Anthropic, `sk-` → OpenAI, 32-char alnum → Mistral, else "Custom") — display + the existing `/settings` PATCH plumbing only; no new backend.
3. **Folder agent**: the PR #19 download rows move here (AgentMenu chip retired). Plus a **one-time centered nudge** ("Point the agent at a folder — your documents stay local") when `/documents` is empty.
4. **Advanced** (collapsed accordion): the entire current settings table, unchanged behavior.

## Plan (each task: implement → `npm run build && npm run lint` clean → coordinator Chrome QA on :5174 → fix round → commit)

### Task U1: app shell — topbar + 100svh grid + hero collapse
**Files:** `web/src/App.tsx`, `web/src/App.css`, new `web/src/TopBar.tsx`
- [ ] Replace page layout with the grid above; topbar (mark, spacer, History, New chat, Library, System buttons — chips retired); hero shown only when the active conversation is empty; conversation pane is the only scroll container; composer fixed. Search|Chat tabs + Search/Documents cards removed (Search.tsx/Ingest.tsx stay in-tree until U3/U2 absorb their logic, unmounted). Keep SlashField.
- [ ] Chrome QA gate: no page scrollbar at 1440×900 and 1280×720; topbar always visible mid-conversation; hero ↔ topbar collapse smooth; drawers/History all open+close (Escape included) with nothing obscured.
- [ ] Commit `feat(web): workbench shell — topbar, viewport grid, hero empty-state (D57)`.

### Task U2: composer — attach/drop ingest + grounding toggle
**Files:** new `web/src/Composer.tsx`, `web/src/Chat.tsx`, `web/src/App.css`
- [ ] Composer per design (`＋` + hidden file input + window dragover overlay; strict⇄open toggle replacing the 3 pills; Hybrid gone from UI). Ingest turns in-stream with per-file outcomes incl. failures (`results[].status/detail`). Multi-file uploads batch like today.
- [ ] Chrome QA gate: drop 2 files (1 good, 1 corrupt xlsx from Acme) → ingest turn shows 1 indexed + 1 failed WITH the reason; toggle persists; old toggles gone.
- [ ] Commit `feat(web): composer — in-chat ingest + strict/open toggle (D57)`.

### Task U3: Find mode — retrieval-only turns
**Files:** `web/src/Composer.tsx`, `web/src/Chat.tsx`, new `web/src/FindTurn.tsx`
- [ ] `Ask|Find` segment; Find calls `/search` (recap off, wide K) via api.ts; find turn renders ranked rows (title/snippet/score/path/modified_at), top match `--accent` tint, row click expands passage; stored in the same conversation stream (client-side turn — no `/v1/answer` call, no persistence server-side; History reload skips find turns gracefully).
- [ ] Chrome QA gate: "schedule" in Find mode → clean list, top hit tinted, zero LLM latency; Ask mode unchanged.
- [ ] Commit `feat(web): Find mode — retrieval-only turns, RAG-first (D57)`.

### Task U4: living logo = status + streaming polish
**Files:** `web/src/App.tsx`/`TopBar.tsx`/`Chat.tsx`, `web/src/App.css`
- [ ] The logo mark animates while a request/stream is in flight (topbar when collapsed, hero when empty); remove any other spinner; `prefers-reduced-motion` → static mark + subtle opacity pulse.
- [ ] Chrome QA gate: visible during an Ask stream; stops on done/error.
- [ ] Commit `feat(web): logo-as-status loading indicator (D57)`.

### Task U5: Library → left drawer; History/Escape/z-index hygiene
**Files:** `web/src/Library.tsx`, `web/src/ChatHistory.tsx`, `web/src/App.css`
- [ ] Library slides from left via topbar toggle (state persisted); ChatHistory gains Escape + its ✕ unobscured (topbar replaces floating chips — verify stacking clean); floating Library pill removed.
- [ ] Chrome QA gate: both drawers open/close via button, Escape, backdrop; no overlap with topbar at any width ≥1024.
- [ ] Commit `fix(web): left Library drawer, drawer hygiene (D57; closes the chip z-index bug)`.

### Task U6: System drawer — simple-first + Advanced accordion + agent section
**Files:** `web/src/SystemMenu.tsx`, `web/src/AgentMenu.tsx` (absorbed), `web/src/App.css`
- [ ] Reorganize per design (Connection / Model+detect badge / Folder agent / Advanced accordion); retire the Agent chip; empty-corpus nudge (dismissable, localStorage); fix stale token-error message.
- [ ] Chrome QA gate: token+URL save round-trip; detect badge correct for a Mistral-shaped and an `sk-ant-` string (typed then cleared — never a real key in screenshots); downloads rows render in System; Advanced opens to the full table.
- [ ] Commit `feat(web): simple-first System drawer, agent section, advanced accordion (D57)`.

### Task U7: token unification + reduced-motion + copy pass
**Files:** `web/src/index.css`, `web/src/App.css`, all components
- [ ] `--accent-ui: #7c5cff` (+hover `#6a45f0`) added to tokens; every hard-coded hex swapped to vars (visual output unchanged — verify by eye); SlashField + logo respect `prefers-reduced-motion`; empty/error copy per the writing rules (direction, not mood; consistent verbs).
- [ ] Chrome QA gate: before/after screenshots pixel-comparable; `grep -c '#7c5cff' web/src/*.tsx *.css` → 0 outside index.css.
- [ ] Commit `refactor(web): tokenize accents, reduced-motion, copy pass (D57)`.

### Task U8: final sweep — full gates + docs + push
- [ ] `npm run build && npm run lint`; full pytest (RAM-capped service) — backend untouched but gate anyway; coordinator full Chrome walkthrough (both browser :5174 and same-origin :5173 behavior); update this doc's log + human.md status; push branch.
- [ ] Commit `docs(ux-wp): implementation log + QA results`.

## Out of scope (parked)
Tauri shell (parked plan on `feat/tauri-shell` — rebase + revise per D56 when this WP merges), backend provisioning (D53-amended), local LLM catalog, mobile/responsive below 1024px (desktop-first; keep it from *breaking* at 768px but no dedicated mobile design this WP).

## Implementation log
- 2026-07-05: foundations (api.ts+CORS) delegated — see branch commits; dev stack `sift-engine-ux` :8001 / `sift-web-ux` :5174.

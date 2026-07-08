# Dev B Roadmap — Human Digest

> The 2-minute version. Full detail + per-WP history: [`ROADMAP.md`](./ROADMAP.md). Paired companion (enforced).

**Updated:** 2026-07-08 · **Owner:** Quentin (Dev B)

## What we're building
The **surface** of Condense: embed a query → pull a wide candidate set from the vector store → **rerank to the single best** → recap it → serve over an authed FastAPI + a chat-first React UI + a Tauri desktop app, all config-driven. Arthur builds the engine (ingest + storage); we meet at the `VectorStore` port and never block on each other.

## Shipped (archived — see `docs/Quentin/archive/`)
- **v0.1.0** (2026-07-04) — version-aware retrieval (mtime collapse), RAM-safe agent+engine chain, local TEI embeddings, `SiftError`-terminal fallback. D18–D36.
- **v0.2.0** (2026-07-05) — LLM-agnostic toolbox (`ToolRegistry`) + `/v1/answer` tool-calling chat agent + grounding modes (strict/hybrid/open) + rich markdown chat. D37–D51.
- **v0.3.0** (2026-07-06) — chat-first "workbench" UX (Ask|Find modes, composer ingest, left Library, logo-as-status) + `api.ts`/CORS foundations + agent `--json`/SIGTERM sidecar binary + landing page. D53–D59.

## Current — public-hardening/audit wave (done today, 2026-07-08)
The repo went public (MIT, D68). A full tri-review + three follow-on PRs merged to `main` today: `/status` secret redaction + constant-time auth + CI (SAST/web/quality) (#22); loopback-only compose bind by default (#23, D70); master-gated `/v1/tokens` mint/list/revoke (#24, D69); core `SearchOutcome` + AST-based layering test + `chunk_tokenizer=auto` (#25, D72). Suite grew 500→518 green. Supply-chain hardening (D71) is done locally, push pending a token-scope fix.

**In parallel:** the Tauri **desktop app** (`feat/desktop-standalone`, D60–D67 — connect-first shell, PyInstaller server bundle for a no-Docker download, llama.cpp local embeddings) is feature-complete and installed for Quentin's manual validation. Merge → **v0.4.0**, on his word.

## Decisions already taken (see DECISIONS.md)
- **Turso/libSQL native vectors** — no external vector DB (D2).
- **Toolbox is the product** — every consumer (our chat, WorkyTalky, an MCP client) drives the same `ToolRegistry` (D38).
- **Desktop v1 is connect-first**, provisioning (download+launch backend) is the end-state (D53/D56).
- **MIT license** for the public launch (D68).
- Everything behind ports → swappable by config, testable in isolation.

## Risks worth knowing
- **History rewrite pending** — a force-push will scrub confidential pilot-client references from history (main + `feat/desktop-standalone`); Arthur must re-clone fresh afterward, not push from an old clone.
- **`agent/cli.py` parent-death caveat** — open ask to Arthur (channel update 32): unsignalled parent death under `--watch --json` can block forever; two fixes proposed, his call.
- Arthur's `docs/Arthur/` looks frozen at 2026-06-27 — gently flagged, no urgency.

## Status / next action
Desktop WP validation is the only thing blocking v0.4.0. Once merged: resume the provisioning phase (download+launch backend from the website) per D56's sequencing.

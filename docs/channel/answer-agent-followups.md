# Answer agent + citations: state as of 2026-08-18 evening

Two local branches, both committed, NOT pushed, NOT merged:

- `fix/answer-agent-resilience` (main checkout)  commit 2611228   575 tests green
- `feat/clickable-citations`   (worktree .claude/worktrees/citations)  commit 100470e   545 tests green

## Why they exist
Live demo 2026-08-18: Mistral free tier 429 -> auto tool mode set the sticky prompted fallback
for the whole process -> two-part question -> raw {"tool": ...} JSON streamed to the user, and
"ran out of tool-call budget" stubs. Both fixed on the first branch. Second branch: citations
and source cards are clickable, deep-link to the document via metadata.source_url, unverified
citations are marked.

## Audit residue (four Opus passes; everything HIGH is closed, these are what remains)
A (answer agent)
- LOW: prose that EXPLAINS a registered tool with a literal example object executes it
  (deliberate registry-first trade, D9). Only in prompted mode.
- LOW: native mode content that is itself a control object is delivered verbatim (model
  misbehaving in native mode; no guard). Cheap to add: parse content, apply _is_control_shaped.
- INFO: json-mode give-up envelope: `raw` is now redacted only via the protocol check upstream;
  re-check after the fourth-pass fix that a rejected protocol payload is not echoed in `raw`.
B (citations)
- MEDIUM (fix first): ChatMarkdown's `a` override trusts href.startsWith('#cite-'); a model can
  write [any text](#cite-0) and borrow the verified style. Mark plugin-built link nodes with
  data.hProperties (e.g. data-citation="n") in citations.ts and check that prop instead.
- LOW: visitor is LIFO across blocks so #cite-N is reverse document order (resolution still
  correct); add 'image' to SKIP_TYPES; splice-with-spread caps at ~62k citations per node
  (use concat); groups over 400 chars are not linkified.

## Next steps (agreed with Quentin)
1. Fix B-1 above (10 lines), rerun the SSR check under scratchpad/audit3/ssr.
2. Per-page parser: PDF/PPTX emit one Page per page/slide behind the existing Parser port
   (adapters/parsing/markitdown.py:126 collapses to Page(number=1)); chunker already tracks
   pages (chunking/token.py:129). Regression test: 3-page PDF -> chunks on pages 1..3.
3. Desktop release: merge main + both branches + feat/desktop-standalone, rebuild the AppImage
   (condense-tauri-builder image exists; check RAM first, box is OOM-sensitive), install.
4. Re-ingest GESDOC into the DESKTOP engine with source_url from
   ~/Documents/GESDOC/condense_demo/manifest.jsonl (scratchpad/reingest_with_urls.sh has a
   --via-v1 mode that works against the OLD engine too). ~28 min on llama-server. Delete then
   re-ingest: dedup keeps old metadata on identical bytes (pinned test).
5. Verify in the desktop UI, not curl.

## Immediate
The desktop app's engine has been the same degraded process since 12:07 today (PID 315686).
Restart the Condense desktop app to clear the sticky prompted mode until the rebuild ships.

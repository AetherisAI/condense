# Condense — landing page

The public front door for Condense: a single-page, self-contained marketing site that
matches the app's exact look (purple accent, system-ui + monospace, the animated "many → one"
mark, and the interactive slash-field background — all reused from `web/src/`).

Two calls to action: **View on GitHub** and **Download** (points at
[Releases](https://github.com/AetherisAI/condense/releases), the future home of the packaged,
Ollama-style installer).

## Files
- `index.html` — the whole page (inline CSS + inline JS, zero dependencies, no build step).
- `favicon.svg` — copy of `web/public/favicon.svg`.

## Preview
Open `index.html` directly in a browser — no server needed:
```bash
open index.html          # macOS
```

## Deploy (GitHub Pages)
Serve this folder as a static site. E.g. GitHub Pages from `/site` on the default branch, or
copy `index.html` + `favicon.svg` into any static host / `web/public/` — it's self-contained
either way.

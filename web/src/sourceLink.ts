import { collapseWhitespace } from './sourceSnippet'

/**
 * Deep-link URL building for a source card's "Open" affordance (front-end only) — the reserved
 * `metadata.source_url` key an ingested file MAY carry (per-file `Source.metadata`, threaded
 * from ingest through `Hit.metadata` to every search/answer response —
 * `src/sift/api/schemas.py::Source.metadata`). `SourcesPanel` (`Chat.tsx`) calls
 * `buildSourceHref` once per card; a `null` result means "no `source_url` set" and the card
 * renders without a link at all — never a broken href.
 *
 * The three deep-link rules:
 *   - a `.pdf` URL                    -> `#page=N` (N falls back to 1 when the source's own page
 *                                        is unknown/0 — a PDF viewer has no "unknown page"),
 *                                        appended to whatever fragment the ingest-supplied URL
 *                                        already carries, UNLESS it already carries its own
 *                                        `page=` — in which case that's a deliberate ingest-time
 *                                        choice this module shouldn't second-guess (F6: this used
 *                                        to unconditionally drop any existing fragment, which was
 *                                        inconsistent with the html branch just below).
 *   - an http(s) `.html`/no-ext URL   -> a URL text fragment (`#:~:text=...`; Chrome/Edge/Firefox
 *                                        131+ scroll to and highlight it, unsupported browsers
 *                                        just open the page) built from the first ~60 chars of
 *                                        the snippet, whitespace-collapsed and cut at a word
 *                                        boundary, appended to any existing fragment the same way.
 *   - anything else (docx/xlsx/pptx, or a scheme/extension the two rules above don't claim)
 *                                      -> the URL as-is. Office formats can't be deep-linked by
 *                                        any viewer — the card's "Copy passage" button is the
 *                                        honest fallback for those, not something this module
 *                                        needs to know about.
 *
 * Every path above is gated on `isSafeUrl` first (F4): `metadata.source_url` is per-file data an
 * ingest caller supplied (`/ingest`'s metadata form field, `src/sift/api/routes.py::_parse_metadata`
 * validates its JSON *shape* but never its URL *scheme*), so it must never be handed to the
 * browser as an `href` unchecked — a `javascript:`/`vbscript:`/`data:`/`file:` URL, or a
 * protocol-relative `//attacker.example` one, must never reach a rendered anchor.
 */

const TEXT_FRAGMENT_MAX_CHARS = 60

/** Whether `url` is safe to ever hand the browser as a citation card's `href` (F4) — parses (as
 * an ABSOLUTE url; `new URL` requires either an absolute string or a `base` argument, and this
 * call passes no base, so a protocol-relative `//host/path` — which has no scheme of its own —
 * throws and is rejected for free, same as a bare relative path) with an `http:` or `https:`
 * scheme. Everything else — `javascript:`, `vbscript:`, `data:`, `file:`, an unparsable string,
 * or anything else outside those two schemes — is rejected. */
function isSafeUrl(url: string): boolean {
  try {
    const protocol = new URL(url).protocol
    return protocol === 'http:' || protocol === 'https:'
  } catch {
    return false
  }
}

/** The URL's file extension (lowercased, no leading dot), ignoring any query string or fragment
 * — `''` when there isn't one (e.g. a bare directory/page URL). */
function extensionOf(url: string): string {
  const withoutFragmentOrQuery = url.split('#')[0].split('?')[0]
  const match = /\.([a-z0-9]+)$/i.exec(withoutFragmentOrQuery)
  return match ? match[1].toLowerCase() : ''
}

/** `buildSourceHref` already gates every branch on `isSafeUrl` (http/https only), so this is
 * always true by the time it's called — kept as an explicit, self-documenting invariant check
 * rather than folded away, so this branch reads correctly on its own if `isSafeUrl`'s allowed
 * schemes ever change independently of this file's html-branch reasoning. */
function isHttpUrl(url: string): boolean {
  return /^https?:\/\//i.test(url)
}

/** The snippet's first ~60 chars, cut at a word boundary rather than mid-word, for the text
 * fragment's `textStart`. `collapseWhitespace` first — the chat/toolbox answer path's raw
 * snippet can carry uncollapsed newlines (see `sourceSnippet.tsx`'s own file comment), which
 * would otherwise leave stray whitespace inside the fragment. */
function textFragmentPrefix(snippet: string): string {
  const collapsed = collapseWhitespace(snippet)
  if (collapsed.length <= TEXT_FRAGMENT_MAX_CHARS) return collapsed
  const cut = collapsed.slice(0, TEXT_FRAGMENT_MAX_CHARS)
  const lastSpace = cut.lastIndexOf(' ')
  return lastSpace > 0 ? cut.slice(0, lastSpace) : cut
}

/** `encodeURIComponent` plus escaping the one character it leaves raw that the text-fragment
 * syntax treats specially: a literal `-` inside `textStart` can be misread as the `prefix-,` /
 * `,-suffix` boundary marker, so it is percent-encoded too (matching how browsers' own
 * "Copy link to highlight" generators handle it). */
function encodeTextFragment(text: string): string {
  return encodeURIComponent(text).replace(/-/g, '%2D')
}

/** The subset of a source card's fields `buildSourceHref` needs — a plain object rather than
 * `ChatSource` itself so this module stays independent of `Chat.tsx`'s wire types. */
export type LinkableSource = {
  metadata?: Record<string, string> | null
  page: number
  snippet: string
}

/** Builds the card's "Open" href, or `null` when the source carries no `metadata.source_url` —
 * or (F4) that URL isn't safe to hand to the browser (see `isSafeUrl`). */
/** Split at the FIRST `#` only, so a fragment that itself contains `#` is kept whole. */
function splitFragment(url: string): [string, string | undefined] {
  const i = url.indexOf('#')
  return i === -1 ? [url, undefined] : [url.slice(0, i), url.slice(i + 1)]
}

export function buildSourceHref(source: LinkableSource): string | null {
  const url = source.metadata?.source_url
  if (!url || !isSafeUrl(url)) return null
  const ext = extensionOf(url)

  if (ext === 'pdf') {
    const [base, existingHash] = splitFragment(url)
    // Ingest already pinned a page — that's a deliberate choice, not something to override (F6).
    if (existingHash && /(?:^|&)page=/.test(existingHash)) return url
    const page = source.page > 0 ? source.page : 1
    const directive = `page=${page}`
    return existingHash ? `${base}#${existingHash}&${directive}` : `${base}#${directive}`
  }

  if (isHttpUrl(url) && (ext === 'html' || ext === 'htm' || ext === '')) {
    const prefix = textFragmentPrefix(source.snippet)
    if (!prefix) return url
    const [base, existingHash] = splitFragment(url)
    const directive = `:~:text=${encodeTextFragment(prefix)}`
    return existingHash ? `${base}#${existingHash}${directive}` : `${base}#${directive}`
  }

  return url
}

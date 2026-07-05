import type { ReactNode } from 'react'

/**
 * Shared source-card presentation helpers (D49) — used by both Search.tsx's citation card and
 * Chat.tsx's `SourcesPanel` so a citation reads identically no matter which backend path produced
 * it.
 *
 * `/search` already whitespace-collapses + truncates its snippet server-side
 * (`pipelines/search.py::_snippet()`), but the chat/toolbox path
 * (`pipelines/answer.py::_merge_sources`) still sends a raw `text[:200]` — whatever
 * whitespace/newlines the parser produced, uncollapsed. Rather than touch that pipeline file
 * mid-slice (co-owned, and the parsing/chunking agent is working nearby), both renderers
 * normalize on the frontend before display: cheap, avoids the collision, and is provably
 * idempotent — re-collapsing an already-collapsed string is a no-op.
 */

/** Collapses runs of whitespace/newlines to a single space and trims. Idempotent — safe to apply
 * to a snippet that's already collapsed (e.g. `/search`'s). */
export function collapseWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/** A page badge is only meaningful once a parser can actually emit page > 1 — today every parser
 * flattens output to a single `Page(1)`, so "p. 1" is pure noise. This single predicate is the
 * one place that gates it; it self-activates the day a paginated parser lands, no UI change
 * needed. */
export function showPageBadge(page: number): boolean {
  return page > 1
}

/** Function words too common to mean anything as a bolded "match" — small and English-biased on
 * purpose, since this is a cosmetic highlight, not a retrieval feature. */
const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'nor', 'of', 'to', 'in', 'on', 'for', 'with', 'without',
  'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
  'this', 'that', 'these', 'those', 'it', 'its', 'as', 'at', 'by', 'from', 'into',
  'than', 'then', 'so', 'but', 'if', 'not', 'no', 'do', 'does', 'did', 'done',
  'can', 'could', 'should', 'would', 'will', 'shall', 'may', 'might', 'must',
  'about', 'what', 'which', 'who', 'whom', 'whose', 'how', 'when', 'where', 'why',
  'you', 'your', 'yours', 'i', 'me', 'my', 'mine', 'we', 'us', 'our', 'ours',
  'they', 'them', 'their', 'theirs', 'he', 'him', 'his', 'she', 'her', 'hers',
  'all', 'any', 'some', 'each', 'other', 'such', 'only', 'own', 'same', 'just',
])

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** The distinct, non-trivial terms worth bolding from a user's query: unicode-aware word split,
 * de-duped case-insensitively, stopwords and very short (<3 char) tokens dropped, longest first
 * so e.g. "invoice" is tried before a shorter term that might otherwise shadow part of it. */
function significantTerms(query: string): string[] {
  const seen = new Set<string>()
  const terms: string[] = []
  for (const raw of query.split(/[^\p{L}\p{N}]+/u)) {
    if (raw.length < 3) continue
    const lower = raw.toLowerCase()
    if (STOPWORDS.has(lower) || seen.has(lower)) continue
    seen.add(lower)
    terms.push(raw)
  }
  return terms.sort((a, b) => b.length - a.length)
}

/**
 * Bolds literal, case-insensitive, whole-word-ish occurrences of `query`'s significant terms
 * inside `text`. Returns React nodes — never raw HTML/`dangerouslySetInnerHTML` — so it composes
 * safely with the plain (non-markdown) snippet blockquotes; a `<mark>` element as a child is just
 * as escaped as a plain text child would be. Pure client-side cosmetic polish: no pipeline change,
 * no effect on retrieval/rerank/ranking.
 */
export function highlightQueryTerms(text: string, query: string): ReactNode {
  const terms = significantTerms(query)
  if (terms.length === 0) return text
  const pattern = new RegExp(
    `(?<![\\p{L}\\p{N}_])(${terms.map(escapeRegExp).join('|')})(?![\\p{L}\\p{N}_])`,
    'giu',
  )
  const parts = text.split(pattern)
  if (parts.length <= 1) return text
  return parts.map((part, i) => (i % 2 === 1 ? <mark className="snippet-hit" key={i}>{part}</mark> : part))
}

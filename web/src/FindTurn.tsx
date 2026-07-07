import { memo, useCallback, useMemo, useState } from 'react'
import { collapseWhitespace, highlightQueryTerms, showPageBadge } from './sourceSnippet'

/**
 * Find mode (D57/Task U3) — retrieval-only turns rendered client-side, NO LLM involved. Backed
 * by `POST /v1/tools/search` (`pipelines.tools`'s raw retrieval primitive: embed → `store.search`,
 * same registry `/v1/answer`'s own `search` tool call renders from — never a parallel search
 * path). This file owns the `FindTurn`/`FindHit` types + their renderer; `Composer.tsx` only needs
 * the types to shape its `onFindStart`/`onFindUpdate` callbacks, and `Chat.tsx` folds the turn
 * into its own `Turn` union (discriminated by `role: 'find'`, same pattern as `IngestTurn`).
 */

/** One ranked passage as returned by `POST /v1/tools/search` (mirrors api.schemas.ToolSearchHit —
 * see `src/sift/api/schemas.py`). No recap, no summary: this IS the raw hit. */
export type FindHit = {
  text: string
  source_path: string
  page: number
  source_hash: string
  index: number
  score: number
  modified_at: string | null
  metadata: Record<string, string> | null
}

/** A client-side-only turn (never sent to `/v1/answer`, never persisted — same mechanism as
 * `IngestTurn`): `turnsFromDetail` in `Chat.tsx` only ever rebuilds user/assistant turns from
 * server history, so a Find turn naturally drops out on reload/reopen — by design, not a bug. */
export type FindTurn = {
  id: string
  role: 'find'
  query: string
  hits: FindHit[]
  /** Set only when the request itself failed (network/HTTP error) — an empty `hits` array with
   * `error: null` is the normal "no matches" case, rendered as the empty-state copy instead. */
  error: string | null
}

/** Just the file name, matching every other citation renderer's convention (Search.tsx/Chat.tsx). */
function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

/** A short, locale-formatted date for the quiet "modified" chip (e.g. "Jul 5, 2026"). Returns
 * `null` on anything unparsable so a malformed value omits the chip rather than showing "Invalid
 * Date" — this is a cosmetic chip, never worth a hard failure. */
function formatModifiedAt(value: string): string | null {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

/** One ranked row: rank badge, filename/page/score/date head, and a click-to-expand snippet. A
 * `<div role="button">` rather than a native `<button>` (matching `Ingest.tsx`'s dropzone
 * pattern) since the row's content — badges + a `<blockquote>` — isn't valid inside a real
 * `<button>`'s phrasing-content-only model. */
const FindRow = memo(function FindRow({
  hit,
  rank,
  index,
  query,
  expanded,
  onToggle,
}: {
  hit: FindHit
  rank: number
  index: number
  query: string
  expanded: boolean
  onToggle: (index: number) => void
}) {
  // Rebuilding the unicode highlight RegExp + splitting the snippet is the row's costliest work;
  // memoize it (and the whitespace-collapse) so it runs only when the hit text or query changes,
  // not on every parent render (the whole thread re-renders on each streamed answer token).
  const snippet = useMemo(() => collapseWhitespace(hit.text), [hit.text])
  const highlighted = useMemo(() => highlightQueryTerms(snippet, query), [snippet, query])
  const modified = hit.modified_at ? formatModifiedAt(hit.modified_at) : null
  const toggle = () => onToggle(index)
  return (
    <div
      className={`find-row${rank === 1 ? ' find-row-top' : ''}`}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onClick={toggle}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          toggle()
        }
      }}
    >
      <span className="find-rank" aria-hidden="true">
        {rank}
      </span>
      <span className="find-row-body">
        <span className="source-head">
          <span className="source-path" title={hit.source_path}>
            {fileName(hit.source_path)}
          </span>
          {showPageBadge(hit.page) && <span className="badge badge-page">p. {hit.page}</span>}
          <span className="badge badge-score">{(hit.score * 100).toFixed(0)}% match</span>
          {modified && <span className="badge badge-date">{modified}</span>}
        </span>
        {snippet && (
          <blockquote className={`snippet${expanded ? '' : ' snippet-clamp find-snippet-clamp'}`}>
            “{highlighted}”
          </blockquote>
        )}
      </span>
    </div>
  )
})

/** Renders one Find turn — the query + its ranked list, or the empty-state copy when the corpus
 * has nothing for it (D57/Task U3: retrieval never hard-fails on "no match", so an empty `hits`
 * array is the normal shape of "nothing relevant", not an error). */
export const FindTurnCard = memo(function FindTurnCard({ turn }: { turn: FindTurn }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  // Stable across renders so `FindRow`'s `React.memo` holds: toggling one row then only
  // re-renders that row, and a streaming answer (which re-renders the whole thread per token)
  // skips this whole card entirely, since `turn` is a stable reference for untouched turns.
  const toggle = useCallback((i: number) => {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }))
  }, [])

  return (
    <div className="chat-turn chat-find">
      <p className="find-turn-head">
        {turn.hits.length > 0
          ? `${turn.hits.length} result${turn.hits.length === 1 ? '' : 's'} for “${turn.query}”`
          : `Find: “${turn.query}”`}
      </p>

      {turn.error && <p className="error">{turn.error}</p>}

      {!turn.error && turn.hits.length === 0 && (
        <p className="empty">
          No matches in your corpus for that. Try different words, or add documents with ＋.
        </p>
      )}

      {turn.hits.length > 0 && (
        <div className="find-results">
          {turn.hits.map((hit, i) => (
            <FindRow
              key={`${hit.source_hash}-${hit.index}`}
              hit={hit}
              rank={i + 1}
              index={i}
              query={turn.query}
              expanded={!!expanded[i]}
              onToggle={toggle}
            />
          ))}
        </div>
      )}
    </div>
  )
})

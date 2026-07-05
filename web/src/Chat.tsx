import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import ChatHistory from './ChatHistory'
import ChatMarkdown from './markdown/ChatMarkdown'
import Logo from './Logo'
import { collapseWhitespace, highlightQueryTerms, showPageBadge } from './sourceSnippet'
import { apiFetch } from './api'

/** Grounding mode (D46) — the trust boundary between the corpus and the model's own general
 * knowledge. Mirrors ``api.schemas.AnswerRequest.grounding``/``Settings.answer_grounding_
 * default``: "strict" answers only from the documents; "hybrid" may add labeled general
 * knowledge; "open" is an unrestricted general assistant. */
type GroundingMode = 'strict' | 'hybrid' | 'open'

/** One ordered slice of an answer (D48) — the structured sibling of `fromGeneralKnowledge`:
 * WHICH parts of the answer are grounded in the ingested documents vs the model's own general
 * knowledge, not just THAT some part is. Mirrors `api.schemas.GroundingSegment`. */
type GroundingSegment = { text: string; kind: 'grounded' | 'general_knowledge' }

/** One SSE frame from ``POST /v1/answer`` (mirrors ``pipelines.answer.AnswerEvent.to_dict()``). */
type AnswerEvent =
  | { type: 'thinking'; [key: string]: unknown }
  | { type: 'tool_call'; tool: string; args_summary: string; args: Record<string, unknown> }
  | { type: 'tool_result'; tool: string; summary: string; detail: unknown }
  | { type: 'answer_delta'; text: string }
  | { type: 'sources'; items: RawSource[] }
  | {
      type: 'grounding'
      grounding_used: GroundingMode
      from_general_knowledge: boolean
      segments: GroundingSegment[]
    }
  | { type: 'done'; conversation_id: string; truncated: boolean }

type TimelineStatus = 'active' | 'done'

/** One tool-call/tool-result pair rendered as a single quiet activity line. */
type TimelineEntry = {
  id: string
  tool: string
  args: Record<string, unknown>
  status: TimelineStatus
  resultSummary?: string
  resultDetail?: unknown
  expanded: boolean
}

/** The compact shape the backend's ``sources`` event/field carries (WP v0.2.0 T6, D42). */
type RawSource = { path: string; page: number; score: number; snippet: string }

/** A citation surfaced from the ``sources`` event — same shape the Search panel renders, plus
 * its own per-card clamp/expand state. */
type ChatSource = RawSource & { expanded: boolean }

type UserTurn = { id: string; role: 'user'; text: string }

type AssistantTurn = {
  id: string
  role: 'assistant'
  text: string
  // The user's question this turn answers (D49) — carried alongside the turn purely so the
  // source cards can bold the query terms they actually match, without threading a separate
  // "current query" prop through the render tree the way Search.tsx's single-result view can.
  question: string
  timeline: TimelineEntry[]
  timelineOpen: boolean
  streaming: boolean
  truncated: boolean
  error: string | null
  sources: ChatSource[]
  sourcesOpen: boolean
  // Grounding (D46) — which mode actually answered this turn, and whether the pipeline
  // detected any content it flags as drawn from the model's own knowledge rather than the
  // corpus. `null`/`false` until the `grounding` SSE event arrives for a turn still streaming
  // live; for a turn reloaded from history (D51/BUG-B) this comes from that turn's OWN
  // persisted `grounding_used`/`from_general_knowledge` instead — immutable per turn, never
  // recomputed from whichever mode the pill is currently on.
  groundingUsed: GroundingMode | null
  fromGeneralKnowledge: boolean
  // Structured grounding segments (D48/BUG-2) — same live-vs-persisted availability as the two
  // fields above (D51/BUG-B: persisted per turn on reload, not reset to empty). Empty until the
  // `grounding` event arrives (or the turn's own history data is loaded); the answer then
  // renders segment-by-segment instead of as one plain markdown blob, so general-knowledge
  // content can be marked BLATANTLY.
  groundingSegments: GroundingSegment[]
}

type Turn = UserTurn | AssistantTurn

/** One turn as returned by ``GET /v1/conversations/{id}`` (mirrors
 * ``api.schemas.ConversationTurnOut``). ``grounding_used``/``from_general_knowledge``/
 * ``grounding_segments`` (D51) are the SAME per-turn immutable fields the live ``grounding`` SSE
 * event carries — persisted on the assistant turn at receive time, so a reopened conversation
 * renders THIS turn's own recorded grounding instead of losing it on every reload (BUG-B). */
type ConversationTurnOut = {
  role: string
  content: string
  turn: number
  created_at: string
  sources: RawSource[] | null
  grounding_used: GroundingMode | null
  from_general_knowledge: boolean
  grounding_segments: GroundingSegment[]
}

/** ``GET /v1/conversations/{id}``'s response shape (mirrors ``api.schemas.
 * ConversationDetailResponse``). */
type ConversationDetail = {
  conversation_id: string
  title: string | null
  created_at: string
  updated_at: string
  turns: ConversationTurnOut[]
}

/** Persists which conversation is "current" across a tab switch (P2) — Chat unmounts when the
 * Search tab is active, so a plain `useState` alone would lose it; refetching the conversation
 * on remount is simpler and cheaper than lifting the whole thread's state up into `App`. */
const STORAGE_KEY = 'chatConversationId'

/** Persists the chosen grounding mode across reloads (D46) — same convention as Search.tsx's
 * `searchMode`/`recapEnabled` localStorage toggles. */
const GROUNDING_STORAGE_KEY = 'chatGrounding'

const GROUNDING_LABELS: Record<GroundingMode, string> = {
  strict: 'Strict',
  hybrid: 'Hybrid',
  open: 'Open',
}

const GROUNDING_HINTS: Record<GroundingMode, string> = {
  strict: "Answers ONLY from your documents — abstains honestly if they don't cover it.",
  hybrid: 'May add general knowledge too, clearly labeled and flagged when it does.',
  open: 'Unrestricted general assistant — uses your documents when useful, not required.',
}

function isGroundingMode(value: string | null): value is GroundingMode {
  return value === 'strict' || value === 'hybrid' || value === 'open'
}

/** The 3-state Strict/Hybrid/Open selector — visually a compact segmented pill, the same
 * language as the Search/Chat tab bar (`.tabs`/`.tab-btn`), scaled down for a header control. */
function GroundingSelector({
  value,
  onChange,
}: {
  value: GroundingMode
  onChange: (mode: GroundingMode) => void
}) {
  return (
    <div className="grounding-select" role="radiogroup" aria-label="Grounding mode">
      {(['strict', 'hybrid', 'open'] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          role="radio"
          aria-checked={value === mode}
          className={`grounding-btn${value === mode ? ' active' : ''}`}
          title={GROUNDING_HINTS[mode]}
          onClick={() => onChange(mode)}
        >
          {GROUNDING_LABELS[mode]}
        </button>
      ))}
    </div>
  )
}

/** Just the file name, matching Search.tsx's citation display. */
function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

function SearchGlyph() {
  return (
    <svg className="tl-glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="4.6" stroke="currentColor" strokeWidth="1.4" />
      <line x1="10.4" y1="10.4" x2="14" y2="14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function ListGlyph() {
  return (
    <svg className="tl-glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="2.6" cy="4" r="1" fill="currentColor" />
      <circle cx="2.6" cy="8" r="1" fill="currentColor" />
      <circle cx="2.6" cy="12" r="1" fill="currentColor" />
      <line x1="5.6" y1="4" x2="13.4" y2="4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="5.6" y1="8" x2="13.4" y2="8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <line x1="5.6" y1="12" x2="13.4" y2="12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function DocGlyph() {
  return (
    <svg className="tl-glyph" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="3.5" y="2" width="9" height="12" rx="1.3" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5.7" y1="5.5" x2="10.3" y2="5.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <line x1="5.7" y1="8" x2="10.3" y2="8" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <line x1="5.7" y1="10.5" x2="8.6" y2="10.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
    </svg>
  )
}

function SparkleGlyph() {
  return (
    <svg className="tl-glyph" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 1.4l1.5 4.1 4.1 1.5-4.1 1.5L8 12.6 6.5 8.5 2.4 7l4.1-1.5z" />
    </svg>
  )
}

function iconFor(tool: string) {
  if (tool === 'search') return <SearchGlyph />
  if (tool === 'list_documents') return <ListGlyph />
  if (tool === 'get_document_chunks') return <DocGlyph />
  return <SparkleGlyph />
}

/** The line's short human phrasing (before the ` · result` suffix, appended separately). */
function humanLabel(entry: TimelineEntry): string {
  if (entry.tool === 'search') {
    const query = entry.args.query
    return `Searching: ${typeof query === 'string' ? query : '…'}`
  }
  if (entry.tool === 'list_documents') return 'Listing documents'
  if (entry.tool === 'get_document_chunks') {
    const hash = entry.args.source_hash
    const short = typeof hash === 'string' ? hash.slice(0, 8) : ''
    return `Reading document${short ? ` ${short}` : ''}`
  }
  return entry.tool
}

const TOOL_NOUNS: Record<string, [string, string]> = {
  search: ['search', 'searches'],
  list_documents: ['listing', 'listings'],
  get_document_chunks: ['read', 'reads'],
}

/** Condensed one-liner for a finished turn's collapsed timeline, e.g. "2 searches · 1 listing". */
function timelineSummary(timeline: TimelineEntry[]): string {
  const counts = new Map<string, number>()
  for (const entry of timeline) counts.set(entry.tool, (counts.get(entry.tool) ?? 0) + 1)
  const parts = [...counts.entries()].map(([tool, n]) => {
    const [singular, plural] = TOOL_NOUNS[tool] ?? [tool, `${tool}s`]
    return `${n} ${n === 1 ? singular : plural}`
  })
  return parts.join(' · ')
}

/** The backend already dedupes/sorts/caps the ``sources`` event — just carry each item's own
 * per-card ``expanded`` state across re-renders of the same turn. */
function toChatSources(items: RawSource[]): ChatSource[] {
  return items.map((item) => ({ ...item, expanded: false }))
}

/** Turn a persisted conversation (``GET /v1/conversations/{id}``) into thread state. Tracks the
 * most recent user message while walking the turns in order so each assistant turn can carry
 * along the question its sources actually answer (D49 — for query-term highlighting).
 *
 * Grounding fields (D51/BUG-B) are read from THIS turn's own persisted data, never from the
 * live `grounding` pill state — a reopened conversation (tab switch, History reopen, page
 * reload) must render each message's own recorded marking, immutably, regardless of whichever
 * mode happens to be selected right now. Before D51 these were unconditionally reset to
 * null/false/[] here because the backend didn't persist them, which is what actually made the
 * purple general-knowledge marking appear to vanish after any remount. */
function turnsFromDetail(detail: ConversationDetail): Turn[] {
  let lastQuestion = ''
  return detail.turns.map((turn) => {
    if (turn.role === 'user') {
      lastQuestion = turn.content
      return { id: crypto.randomUUID(), role: 'user', text: turn.content } satisfies UserTurn
    }
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      text: turn.content,
      question: lastQuestion,
      timeline: [],
      timelineOpen: false,
      streaming: false,
      truncated: false,
      error: null,
      sources: toChatSources(turn.sources ?? []),
      sourcesOpen: false,
      groundingUsed: turn.grounding_used,
      fromGeneralKnowledge: turn.from_general_knowledge,
      groundingSegments: turn.grounding_segments ?? [],
    } satisfies AssistantTurn
  })
}

/** Read a ``text/event-stream`` body, calling ``onEvent`` for each decoded frame, in order. */
async function readSse(body: ReadableStream<Uint8Array>, onEvent: (evt: AnswerEvent) => void) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!line) continue
      try {
        onEvent(JSON.parse(line.slice(6)) as AnswerEvent)
      } catch {
        // A malformed frame is skipped rather than aborting the whole stream.
      }
    }
  }
}

function TimelineLine({ entry, onToggle }: { entry: TimelineEntry; onToggle: () => void }) {
  const hasDetail = Object.keys(entry.args).length > 0 || entry.resultDetail !== undefined
  return (
    <div className={`tl-line${entry.status === 'active' ? ' tl-active' : ''}`}>
      <button
        type="button"
        className="tl-toggle"
        onClick={onToggle}
        aria-expanded={entry.expanded}
        disabled={!hasDetail}
      >
        <span className="tl-chevron" aria-hidden="true">
          {hasDetail ? '›' : ''}
        </span>
        <span className="tl-icon">{iconFor(entry.tool)}</span>
        <span className="tl-text">
          {humanLabel(entry)}
          {entry.resultSummary && <span className="tl-result"> · {entry.resultSummary}</span>}
        </span>
      </button>
      {entry.expanded && (
        <pre className="json tl-detail">
          <code>{JSON.stringify({ args: entry.args, result: entry.resultDetail }, null, 2)}</code>
        </pre>
      )}
    </div>
  )
}

/** A collapsed-by-default "N sources · expand" pill (styled like the activity timeline's own
 * summary pill) that opens into compact citation cards — filename, page, match %, snippet
 * clamped to ~3 lines with its own per-card expand. Never a full source wall by default. */
function SourcesPanel({
  sources,
  query,
  open,
  onToggleOpen,
  onToggleCard,
}: {
  sources: ChatSource[]
  /** The question these sources answer — used only to bold the query terms it matches within
   * each snippet (D49); never sent anywhere, purely a display concern. */
  query: string
  open: boolean
  onToggleOpen: () => void
  onToggleCard: (index: number) => void
}) {
  if (!open) {
    return (
      <button type="button" className="tl-summary sources-summary" onClick={onToggleOpen}>
        {sources.length} source{sources.length === 1 ? '' : 's'}
        <span className="tl-summary-more">expand</span>
      </button>
    )
  }
  return (
    <div className="chat-sources">
      <button type="button" className="tl-summary sources-summary" onClick={onToggleOpen}>
        {sources.length} source{sources.length === 1 ? '' : 's'}
        <span className="tl-summary-more">collapse</span>
      </button>
      {sources.map((s, i) => {
        const snippet = collapseWhitespace(s.snippet)
        return (
          <div className="source source-compact" key={`${s.path}-${s.page}-${i}`}>
            <div className="source-head">
              <span className="source-path" title={s.path}>
                {fileName(s.path)}
              </span>
              {showPageBadge(s.page) && <span className="badge badge-page">p. {s.page}</span>}
              <span className="badge badge-score">{(s.score * 100).toFixed(0)}% match</span>
            </div>
            {snippet && (
              <blockquote className={`snippet${s.expanded ? '' : ' snippet-clamp'}`}>
                “{highlightQueryTerms(snippet, query)}”
              </blockquote>
            )}
            {snippet.length > 140 && (
              <button type="button" className="source-expand" onClick={() => onToggleCard(i)}>
                {s.expanded ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Imperative surface exposed to the workbench shell (`App.tsx`) — the topbar's "New chat"
 * button lives outside this component's own tree, so it drives `newChat()` through a ref instead
 * of a prop callback (the function closes over live `turns`/`conversationId` state, which would
 * otherwise need lifting wholesale into `App`). */
export type ChatHandle = { newChat: () => void }

type ChatProps = {
  token: string
  // The History drawer (`ChatHistory`) is still rendered from here — right next to the
  // conversation state it reads/writes — but its OPEN state is controlled from the workbench
  // shell so a single topbar button can trigger it (D57/Task U1: no more floating chips).
  historyOpen: boolean
  onHistoryOpenChange: (open: boolean) => void
  // Lets the topbar show/hide "New chat" the same way the old in-panel header did (only once a
  // conversation has turns) without lifting the whole thread into `App`.
  onTurnsChange?: (hasTurns: boolean) => void
}

/**
 * Chat panel — a thread view over ``POST /v1/answer`` (``stream:true``). Per exchange: the
 * user's bubble, then the streamed ANSWER (always in focus, never pushed below a source wall),
 * then a collapsed sources pill, then the activity timeline's own collapsed summary pill. The
 * current conversation persists across a tab switch (`conversation_id` in `localStorage`,
 * refetched on mount) and a History drawer lists/reopens/deletes past ones.
 */
const Chat = forwardRef<ChatHandle, ChatProps>(function Chat(
  { token, historyOpen, onHistoryOpenChange, onTurnsChange },
  ref,
) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [grounding, setGrounding] = useState<GroundingMode>(() => {
    const stored = localStorage.getItem(GROUNDING_STORAGE_KEY)
    return isGroundingMode(stored) ? stored : 'strict'
  })
  const threadRef = useRef<HTMLDivElement>(null)
  // Auto-scroll pins to the bottom while an answer streams in, but a user who scrolls up to
  // reread something is respected — never yanked back down (P1).
  const pinnedToBottomRef = useRef(true)

  async function fetchConversation(id: string): Promise<ConversationDetail | null> {
    const resp = await apiFetch(`/v1/conversations/${encodeURIComponent(id)}`, token)
    if (!resp.ok) return null
    return (await resp.json()) as ConversationDetail
  }

  // Rehydrate the last-open conversation on mount — the effect that makes switching Search ->
  // Chat -> Search -> Chat keep the same conversation in view (P2) even though this component
  // fully unmounts while the Search tab is active.
  useEffect(() => {
    if (!token) return
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return
    let cancelled = false
    async function rehydrate() {
      const detail = await fetchConversation(stored!).catch(() => null)
      if (cancelled) return
      if (detail) {
        setConversationId(detail.conversation_id)
        setTurns(turnsFromDetail(detail))
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    }
    void rehydrate()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    if (conversationId) localStorage.setItem(STORAGE_KEY, conversationId)
  }, [conversationId])

  // Lets the topbar's "New chat" button (outside this component's tree) drive `newChat` — see
  // the `ChatHandle` comment above.
  useImperativeHandle(ref, () => ({ newChat }))

  // Tells the topbar whether to show "New chat" at all (same gating the old in-panel header
  // used: only once the conversation has turns).
  useEffect(() => {
    onTurnsChange?.(turns.length > 0)
  }, [turns.length, onTurnsChange])

  function setGroundingMode(mode: GroundingMode) {
    setGrounding(mode)
    localStorage.setItem(GROUNDING_STORAGE_KEY, mode)
  }

  useEffect(() => {
    if (!pinnedToBottomRef.current) return
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  function handleThreadScroll() {
    const el = threadRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    pinnedToBottomRef.current = distanceFromBottom < 48
  }

  function patchAssistant(id: string, fn: (t: AssistantTurn) => AssistantTurn) {
    setTurns((prev) => prev.map((t) => (t.id === id && t.role === 'assistant' ? fn(t) : t)))
  }

  function toggleEntry(turnId: string, entryId: string) {
    patchAssistant(turnId, (t) => ({
      ...t,
      timeline: t.timeline.map((e) => (e.id === entryId ? { ...e, expanded: !e.expanded } : e)),
    }))
  }

  function toggleTimelineOpen(turnId: string) {
    patchAssistant(turnId, (t) => ({ ...t, timelineOpen: !t.timelineOpen }))
  }

  function toggleSourcesOpen(turnId: string) {
    patchAssistant(turnId, (t) => ({ ...t, sourcesOpen: !t.sourcesOpen }))
  }

  function toggleSourceCard(turnId: string, index: number) {
    patchAssistant(turnId, (t) => ({
      ...t,
      sources: t.sources.map((s, i) => (i === index ? { ...s, expanded: !s.expanded } : s)),
    }))
  }

  function newChat() {
    setTurns([])
    setConversationId(null)
    setInput('')
    localStorage.removeItem(STORAGE_KEY)
  }

  async function openConversation(id: string) {
    pinnedToBottomRef.current = true
    const detail = await fetchConversation(id).catch(() => null)
    if (!detail) return
    setConversationId(detail.conversation_id)
    setTurns(turnsFromDetail(detail))
  }

  async function send() {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    pinnedToBottomRef.current = true
    const userTurn: UserTurn = { id: crypto.randomUUID(), role: 'user', text }
    const assistantId = crypto.randomUUID()
    const assistantTurn: AssistantTurn = {
      id: assistantId,
      role: 'assistant',
      text: '',
      question: text,
      timeline: [],
      timelineOpen: true,
      streaming: true,
      truncated: false,
      error: null,
      sources: [],
      sourcesOpen: false,
      groundingUsed: null,
      fromGeneralKnowledge: false,
      groundingSegments: [],
    }
    setTurns((prev) => [...prev, userTurn, assistantTurn])
    setBusy(true)

    try {
      const resp = await apiFetch('/v1/answer', token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          format: 'text',
          stream: true,
          grounding,
        }),
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`Chat failed: ${resp.status} ${resp.statusText}`)
      }
      await readSse(resp.body, (evt) => {
        if (evt.type === 'tool_call') {
          patchAssistant(assistantId, (t) => ({
            ...t,
            timeline: [
              ...t.timeline,
              {
                id: crypto.randomUUID(),
                tool: evt.tool,
                args: evt.args ?? {},
                status: 'active',
                expanded: false,
              },
            ],
          }))
        } else if (evt.type === 'tool_result') {
          patchAssistant(assistantId, (t) => {
            const timeline = [...t.timeline]
            for (let i = timeline.length - 1; i >= 0; i--) {
              if (timeline[i].tool === evt.tool && timeline[i].status === 'active') {
                timeline[i] = {
                  ...timeline[i],
                  status: 'done',
                  resultSummary: evt.summary,
                  resultDetail: evt.detail,
                }
                break
              }
            }
            return { ...t, timeline }
          })
        } else if (evt.type === 'answer_delta') {
          patchAssistant(assistantId, (t) => ({ ...t, text: t.text + evt.text }))
        } else if (evt.type === 'sources') {
          patchAssistant(assistantId, (t) => ({ ...t, sources: toChatSources(evt.items) }))
        } else if (evt.type === 'grounding') {
          patchAssistant(assistantId, (t) => ({
            ...t,
            groundingUsed: evt.grounding_used,
            fromGeneralKnowledge: evt.from_general_knowledge,
            groundingSegments: evt.segments ?? [],
          }))
        } else if (evt.type === 'done') {
          setConversationId(evt.conversation_id)
          patchAssistant(assistantId, (t) => ({
            ...t,
            streaming: false,
            timelineOpen: false,
            truncated: evt.truncated,
          }))
        }
        // Any OTHER/unrecognized event type is silently ignored rather than thrown on — new
        // event types must never be able to strand a turn mid-stream (BUG-1/D48).
      })
      // BUG-1/D48 safety net: the backend now guarantees a "done" frame always closes the
      // stream, but this is a second, independent line of defense — if the stream closes for
      // ANY reason without "done" ever having been observed (a dropped connection, a proxy that
      // truncates the response, a future regression), force the turn out of "thinking" instead
      // of leaving it stuck forever. A no-op when "done" already finalized it (the `t.streaming`
      // check below is false in that case).
      patchAssistant(assistantId, (t) =>
        t.streaming ? { ...t, streaming: false, timelineOpen: false, truncated: true } : t,
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      patchAssistant(assistantId, (t) => ({ ...t, streaming: false, timelineOpen: false, error: msg }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="chat-workbench">
      <div className="chat-stream" ref={threadRef} onScroll={handleThreadScroll}>
        <div className="chat-inner">
          {turns.length === 0 ? (
            <div className="hero">
              <Logo />
              <h1 className="hero-word">Condense</h1>
              <p className="hero-tagline">Search across all your knowledge</p>
            </div>
          ) : (
            turns.map((turn) =>
              turn.role === 'user' ? (
                <div className="chat-turn chat-user" key={turn.id}>
                  {turn.text}
                </div>
              ) : (
                <div className="chat-turn chat-assistant" key={turn.id}>
                  {turn.streaming && turn.timeline.length === 0 && !turn.text && (
                    <div className="tl-line tl-active">
                      <span className="tl-icon">
                        <SparkleGlyph />
                      </span>
                      <span className="tl-text">Thinking…</span>
                    </div>
                  )}

                  {turn.error && <p className="error">{turn.error}</p>}

                  {turn.text && (
                    <div className="recap chat-answer">
                      {turn.groundingSegments.length > 0 ? (
                        turn.groundingSegments.map((segment, index) =>
                          segment.kind === 'general_knowledge' ? (
                            <div className="gk-segment" key={index}>
                              <span className="gk-segment-tag">general knowledge</span>
                              <ChatMarkdown text={segment.text} />
                            </div>
                          ) : (
                            <ChatMarkdown text={segment.text} key={index} />
                          ),
                        )
                      ) : (
                        <ChatMarkdown text={turn.text} />
                      )}
                    </div>
                  )}

                  {turn.fromGeneralKnowledge && (
                    <span className="gk-chip" title="This answer contains content the assistant drew from its own general knowledge, not your ingested documents.">
                      from general knowledge — not your documents
                    </span>
                  )}

                  {turn.truncated && (
                    <p className="chat-truncated">Stopped early — ran out of tool-call budget.</p>
                  )}

                  {turn.sources.length > 0 && (
                    <SourcesPanel
                      sources={turn.sources}
                      query={turn.question}
                      open={turn.sourcesOpen}
                      onToggleOpen={() => toggleSourcesOpen(turn.id)}
                      onToggleCard={(index) => toggleSourceCard(turn.id, index)}
                    />
                  )}

                  {turn.timeline.length > 0 &&
                    (turn.timelineOpen ? (
                      <div className="timeline">
                        {turn.timeline.map((entry) => (
                          <TimelineLine
                            key={entry.id}
                            entry={entry}
                            onToggle={() => toggleEntry(turn.id, entry.id)}
                          />
                        ))}
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="tl-summary"
                        onClick={() => toggleTimelineOpen(turn.id)}
                      >
                        {timelineSummary(turn.timeline)}
                        <span className="tl-summary-more">expand</span>
                      </button>
                    ))}
                </div>
              ),
            )
          )}
        </div>
      </div>

      <div className="composer">
        <div className="composer-inner">
          <div className="composer-pills">
            <GroundingSelector value={grounding} onChange={setGroundingMode} />
          </div>
          <div className="row">
            <input
              type="text"
              value={input}
              placeholder="Ask a question…"
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') send()
              }}
            />
            <button type="button" className="btn-primary" onClick={send} disabled={busy || !input.trim()}>
              {busy ? 'Thinking…' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      <ChatHistory
        token={token}
        currentConversationId={conversationId}
        onOpen={openConversation}
        open={historyOpen}
        onOpenChange={onHistoryOpenChange}
      />
    </div>
  )
})

export default Chat

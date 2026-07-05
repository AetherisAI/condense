import { useEffect, useState } from 'react'
import { apiFetch } from './api'

/** One row of ``GET /v1/conversations`` (mirrors api.schemas.ConversationSummary). */
type ConversationSummary = {
  conversation_id: string
  title: string | null
  updated_at: string
  turn_count: number
}

type ConversationListResponse = {
  conversations: ConversationSummary[]
  limit: number
  offset: number
}

/** A quiet relative-time label ("2h ago") — good enough for a history list, no library needed. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const minutes = Math.round((Date.now() - then) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.round(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.round(months / 12)}y ago`
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
      <path
        d="M5.5 2.5h5M2.5 4.5h11M4 4.5l.6 8a1 1 0 0 0 1 1h4.8a1 1 0 0 0 1-1l.6-8M6.5 7v4M9.5 7v4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * History drawer — past ``/v1/answer`` conversations, styled like the Library drawer. Opens on
 * demand (fetches ``GET /v1/conversations`` lazily, same pattern as ``Library.tsx``), highlights
 * whichever conversation is currently open in the Chat panel, and lets the user reopen (click a
 * row) or delete (trash icon, click-again-to-confirm — no native `confirm()` dialog) any of them.
 * Its own trigger chip is gone (D57/Task U1) — `open` is controlled from the workbench topbar,
 * which is the single button that shows/hides this drawer now. Closes on backdrop-click or
 * Escape (D57/Task U5) — see the Escape effect below for the stacking rule it uses so a single
 * Escape press never closes two drawers at once.
 */
export default function ChatHistory({
  token,
  currentConversationId,
  onOpen,
  open,
  onOpenChange,
}: {
  token: string
  currentConversationId: string | null
  onOpen: (conversationId: string) => void
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)

  // Dismiss on Escape while open — outside clicks are caught by the drawer backdrop (same base
  // pattern as System). History is the one drawer every other drawer can be stacked in front of
  // (it's the earliest `.drawer` in document order — nested inside `Chat` — while Library/System
  // both render after it from `App.tsx`, so at equal z-index they paint on top of it). If another
  // drawer is open when Escape is pressed, this yields instead of closing alongside it, so one
  // Escape press closes exactly one drawer rather than the whole stack. Library mirrors System's
  // plain always-close pattern instead (see Library.tsx) since — now that it's the sole LEFT-hand,
  // last-in-DOM drawer — nothing else is ever stacked in front of it. The standalone Agent drawer
  // that used to make this a 4-drawer problem is retired (D57/Task U6 folded it into System), so
  // this now guarantees History never double-closes with anything, Library+History resolves to
  // exactly one close, and System closes alone whenever it's the only drawer open.
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      const openDrawers = document.querySelectorAll('.drawer.open')
      if (openDrawers.length > 1) return // something else is open — let it close first
      onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    async function load() {
      setError(null)
      setLoading(true)
      try {
        const resp = await apiFetch('/v1/conversations', token)
        if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
        const data = (await resp.json()) as ConversationListResponse
        if (cancelled) return
        setConversations(data.conversations)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [open, token])

  // A pending delete-confirm auto-cancels after a few seconds rather than staying armed forever.
  useEffect(() => {
    if (!confirmingId) return
    const timer = setTimeout(() => setConfirmingId(null), 3000)
    return () => clearTimeout(timer)
  }, [confirmingId])

  async function remove(id: string) {
    setConfirmingId(null)
    try {
      const resp = await apiFetch(`/v1/conversations/${encodeURIComponent(id)}`, token, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
      setConversations((prev) => (prev ? prev.filter((c) => c.conversation_id !== id) : prev))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  function select(id: string) {
    onOpenChange(false)
    onOpen(id)
  }

  const count = conversations?.length ?? 0

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={() => onOpenChange(false)} />}

      <aside className={`drawer${open ? ' open' : ''}`} aria-hidden={!open}>
        <div className="drawer-head">
          <h2>History</h2>
          {count > 0 && <span className="drawer-count">{count}</span>}
          <button
            type="button"
            className="drawer-close"
            onClick={() => onOpenChange(false)}
            aria-label="Close history"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {loading && <p className="drawer-muted">Loading…</p>}
          {error && <p className="error">{error}</p>}

          {!loading && !error && conversations && conversations.length === 0 && (
            <p className="drawer-muted">No past conversations yet.</p>
          )}

          {conversations && conversations.length > 0 && (
            <ul className="drawer-list">
              {conversations.map((c) => {
                const active = c.conversation_id === currentConversationId
                const confirming = confirmingId === c.conversation_id
                const label = c.title || 'Untitled conversation'
                return (
                  <li
                    className={`drawer-item history-item${active ? ' history-item-active' : ''}`}
                    data-conversation-id={c.conversation_id}
                    key={c.conversation_id}
                  >
                    <button
                      type="button"
                      className="history-open"
                      onClick={() => select(c.conversation_id)}
                    >
                      <span className="doc-meta">
                        <span className="doc-name" title={label}>
                          {label}
                        </span>
                        <span className="doc-sub">
                          {relativeTime(c.updated_at)} · {c.turn_count} turn
                          {c.turn_count === 1 ? '' : 's'}
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      className={`drawer-del${confirming ? ' drawer-del-confirm' : ''}`}
                      onClick={() =>
                        confirming ? remove(c.conversation_id) : setConfirmingId(c.conversation_id)
                      }
                      aria-label={confirming ? `Confirm delete "${label}"` : `Delete "${label}"`}
                      title={confirming ? 'Click again to confirm' : 'Delete'}
                    >
                      {confirming ? '✓' : <TrashIcon />}
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </aside>
    </>
  )
}

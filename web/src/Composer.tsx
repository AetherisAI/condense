import { useEffect, useRef, useState } from 'react'
import { fmtSize, postIngest } from './ingestClient'
import { persistGrounding, type ComposerGroundingMode } from './grounding'
import { apiFetch } from './api'
import type { FindHit, FindTurn } from './FindTurn'

/**
 * The workbench's composer (D57/Task U2+U3) — extracted out of `Chat.tsx`: the Ask/Find mode
 * segment, the grounding toggle, the input row (attach + text + Send), and in-chat ingest (attach
 * button, hidden multi-file input, and a whole-window drag-drop overlay). Chat still owns the
 * conversation thread — this component only reports intent up (`onSend`, `onGroundingChange`) and
 * drives ingest/find turns into that same thread via their own start/update callback pairs, since
 * both must render inline, in order, alongside the answer/user turns they're siblings of.
 *
 * **Grounding (D46, UI-only change):** the old Strict/Hybrid/Open 3-way pill is now a 2-state
 * `Corpus only ⇄ + General knowledge` toggle. This is a UI simplification ONLY — "hybrid" stays a
 * fully valid value on the wire (`api.schemas.AnswerRequest.grounding`) for other consumers and for
 * conversations that already recorded it; this toggle just never offers it as a choice going
 * forward, and `loadStoredGrounding` migrates anyone's remembered "hybrid" preference to "open"
 * (the bucket the API always treated it closest to for a corpus-first assistant).
 *
 * **Mode (D57/Task U3):** `Ask` is today's `/v1/answer` flow (unchanged). `Find` is retrieval-only
 * — this component itself calls `POST /v1/tools/search` (the toolbox's raw-retrieval primitive,
 * D57's product statement: Find mode IS the toolbox's search tool) and renders a `FindTurn`, no
 * LLM involved. The grounding toggle only means something for Ask, so it's dimmed/disabled (never
 * hidden — layout stability) while Find is active.
 */

type ComposerMode = 'ask' | 'find'

const MODE_STORAGE_KEY = 'composerMode'

function loadStoredMode(): ComposerMode {
  return localStorage.getItem(MODE_STORAGE_KEY) === 'find' ? 'find' : 'ask'
}

/** The compact 2-way segmented toggle for Ask/Find — same visual language/classes as the
 * grounding toggle below (`.grounding-select`/`.grounding-btn` are a generic segmented-pill
 * pattern, not grounding-specific, so both toggles share it rather than duplicating the CSS). */
function ModeToggle({ value, onChange }: { value: ComposerMode; onChange: (mode: ComposerMode) => void }) {
  return (
    <div className="grounding-select" role="radiogroup" aria-label="Composer mode">
      {(['ask', 'find'] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          role="radio"
          aria-checked={value === mode}
          className={`grounding-btn${value === mode ? ' active' : ''}`}
          title={mode === 'ask' ? 'Ask — a conversational answer, with sources.' : 'Find — ranked results from your corpus, no LLM.'}
          onClick={() => onChange(mode)}
        >
          {mode === 'ask' ? 'Ask' : 'Find'}
        </button>
      ))}
    </div>
  )
}

const GROUNDING_LABELS: Record<ComposerGroundingMode, string> = {
  strict: 'Corpus only',
  open: '+ General knowledge',
}

const GROUNDING_HINTS: Record<ComposerGroundingMode, string> = {
  strict: "Answers ONLY from your documents — abstains honestly if they don't cover it.",
  open: 'Uses your documents when useful, plus general knowledge — labeled clearly when it does.',
}

/** The compact 2-way segmented toggle — same visual language/classes as the retired 3-way pill
 * (`.grounding-select`/`.grounding-btn`), so the look carries over unchanged.
 *
 * `disabled` (D57/Task U3) dims the whole control and blocks interaction without unmounting it —
 * grounding only means something for Ask mode, but layout stability means it stays in place
 * (never hidden) while Find is active, with a `title` explaining why. */
function GroundingToggle({
  value,
  onChange,
  disabled = false,
}: {
  value: ComposerGroundingMode
  onChange: (mode: ComposerGroundingMode) => void
  disabled?: boolean
}) {
  return (
    <div
      className={`grounding-select${disabled ? ' is-disabled' : ''}`}
      role="radiogroup"
      aria-label="Grounding mode"
      aria-disabled={disabled}
      title={disabled ? 'Grounding only applies to Ask mode.' : undefined}
    >
      {(['strict', 'open'] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          role="radio"
          aria-checked={value === mode}
          className={`grounding-btn${value === mode ? ' active' : ''}`}
          title={GROUNDING_HINTS[mode]}
          disabled={disabled}
          onClick={() => onChange(mode)}
        >
          {GROUNDING_LABELS[mode]}
        </button>
      ))}
    </div>
  )
}

/** One file's outcome within an ingest turn — `'uploading'` while the batch's single `/ingest`
 * request is in flight, then whatever `results[]` (or a client-side error) settles it to. */
export type IngestOutcomeStatus = 'uploading' | 'indexed' | 'skipped_dedup' | 'failed'

export type IngestFileEntry = {
  id: string
  name: string
  size: number
  status: IngestOutcomeStatus
  chunks?: number | null
  detail?: string | null
}

/** A client-side-only turn (never sent to `/v1/answer`, never persisted — D57/Task U2) rendered
 * inline in the chat stream for one in-chat upload batch. `Chat.tsx` folds this into its own
 * `Turn` union (discriminated by `role: 'ingest'`, the same discriminant the user/assistant turns
 * already use) purely so it renders in the right chronological position among them. */
export type IngestTurn = {
  id: string
  role: 'ingest'
  files: IngestFileEntry[]
}

function asOutcomeStatus(value: string): Exclude<IngestOutcomeStatus, 'uploading'> {
  return value === 'indexed' || value === 'skipped_dedup' ? value : 'failed'
}

function ingestSummary(files: IngestFileEntry[]): string {
  if (files.some((f) => f.status === 'uploading')) {
    return `Adding ${files.length} file${files.length === 1 ? '' : 's'}…`
  }
  const counts = new Map<string, number>()
  for (const f of files) counts.set(f.status, (counts.get(f.status) ?? 0) + 1)
  const labelFor = (status: string, n: number) => {
    if (status === 'indexed') return `${n} indexed`
    if (status === 'skipped_dedup') return `${n} already in your corpus`
    if (status === 'failed') return `${n} failed`
    return `${n} ${status}`
  }
  return [...counts.entries()].map(([status, n]) => labelFor(status, n)).join(' · ')
}

/** The right-hand status line for one file row within an ingest turn. */
function fileStatusLine(entry: IngestFileEntry): string {
  switch (entry.status) {
    case 'uploading':
      return 'Uploading…'
    case 'indexed':
      if (entry.detail) return entry.detail // e.g. "no extractable text" — a soft, non-failure note
      return entry.chunks != null
        ? `Indexed · ${entry.chunks} chunk${entry.chunks === 1 ? '' : 's'}`
        : 'Indexed'
    case 'skipped_dedup':
      return 'Already in your corpus'
    case 'failed':
      return entry.detail ?? 'Failed'
  }
}

/** Renders one ingest turn — a compact card listing every file in the batch with its outcome.
 * Reuses `Ingest.tsx`'s own `.doc-item`/`.doc-badge` styling (including the `.doc-failed` error
 * tint, already built on the `--error*` vars) rather than a parallel design system. */
export function IngestTurnCard({ turn }: { turn: IngestTurn }) {
  return (
    <div className="chat-turn chat-ingest">
      <p className="ingest-turn-head">{ingestSummary(turn.files)}</p>
      <ul className="doc-list">
        {turn.files.map((f) => (
          <li className={`doc-item doc-${f.status}`} key={f.id}>
            <span className="doc-meta">
              <span className="doc-name" title={f.name}>
                {f.name}
              </span>
              <span className="doc-sub">
                {fmtSize(f.size)} · {fileStatusLine(f)}
              </span>
            </span>
            <span className="doc-badge" aria-hidden="true">
              {f.status === 'uploading' && <span className="doc-spinner" />}
              {f.status === 'indexed' && '✓'}
              {f.status === 'skipped_dedup' && '⊘'}
              {f.status === 'failed' && '✕'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export type ComposerProps = {
  token: string
  input: string
  onInputChange: (value: string) => void
  busy: boolean
  onSend: () => void
  grounding: ComposerGroundingMode
  onGroundingChange: (mode: ComposerGroundingMode) => void
  /** Appends a brand-new ingest turn (all files `'uploading'`) to the conversation stream. */
  onIngestStart: (turn: IngestTurn) => void
  /** Patches a previously-started ingest turn (by id) with its files' settled outcomes. */
  onIngestUpdate: (id: string, files: IngestFileEntry[]) => void
  /** Appends a brand-new Find turn (empty `hits`, no error yet) to the conversation stream
   * (D57/Task U3) — mirrors `onIngestStart`'s shape. */
  onFindStart: (turn: FindTurn) => void
  /** Patches a previously-started Find turn (by id) with its settled hits, or an error. */
  onFindUpdate: (id: string, hits: FindHit[], error: string | null) => void
}

export default function Composer({
  token,
  input,
  onInputChange,
  busy,
  onSend,
  grounding,
  onGroundingChange,
  onIngestStart,
  onIngestUpdate,
  onFindStart,
  onFindUpdate,
}: ComposerProps) {
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [mode, setModeState] = useState<ComposerMode>(loadStoredMode)
  const [finding, setFinding] = useState(false)

  function setMode(next: ComposerMode) {
    setModeState(next)
    localStorage.setItem(MODE_STORAGE_KEY, next)
  }

  /** Find mode's send path (D57/Task U3) — retrieval only, no LLM: embeds the query and reranks
   * against the corpus via the toolbox's own search tool. Mirrors `handleFiles`' start/settle
   * shape (append an in-flight turn, then patch it once settled) so a Find turn renders inline
   * the moment it's fired, same as an ingest turn. */
  async function runFind() {
    const query = input.trim()
    if (!query || busy || finding) return
    onInputChange('')
    const turnId = crypto.randomUUID()
    onFindStart({ id: turnId, role: 'find', query, hits: [] as FindHit[], error: null })
    setFinding(true)
    try {
      const resp = await apiFetch('/v1/tools/search', token, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      if (!resp.ok) {
        throw new Error(`Find failed: ${resp.status} ${resp.statusText}`)
      }
      const data = (await resp.json()) as { hits: FindHit[] }
      onFindUpdate(turnId, data.hits, null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      onFindUpdate(turnId, [], msg)
    } finally {
      setFinding(false)
    }
  }

  function handleSend() {
    if (mode === 'find') {
      void runFind()
    } else {
      onSend()
    }
  }

  async function handleFiles(files: File[]) {
    if (files.length === 0) return
    const turnId = crypto.randomUUID()
    const entries: IngestFileEntry[] = files.map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      size: f.size,
      status: 'uploading',
    }))
    onIngestStart({ id: turnId, role: 'ingest', files: entries })

    if (!token) {
      onIngestUpdate(
        turnId,
        entries.map((e) => ({
          ...e,
          status: 'failed',
          detail: 'Set a bearer token in System settings first.',
        })),
      )
      return
    }

    try {
      const data = await postIngest(token, files)
      // The route returns one result per input file, in order — map entries[i] → results[i].
      const updated = entries.map((e, i) => {
        const r = data.results[i]
        if (!r) return { ...e, status: 'failed' as const, detail: 'no result returned' }
        return {
          ...e,
          status: asOutcomeStatus(r.status),
          chunks: r.chunks,
          detail: r.detail,
        }
      })
      onIngestUpdate(turnId, updated)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      onIngestUpdate(
        turnId,
        entries.map((e) => ({ ...e, status: 'failed', detail: msg })),
      )
    }
  }

  // A ref keeps the window-level drag/drop listeners (mounted once, below) always calling the
  // LATEST `handleFiles` closure — re-attaching them on every render would be wasteful, but a
  // stale closure would silently ingest into a torn-down turn/token from a previous render.
  const handleFilesRef = useRef(handleFiles)
  handleFilesRef.current = handleFiles

  useEffect(() => {
    let dragDepth = 0

    function hasFiles(e: DragEvent): boolean {
      return Array.from(e.dataTransfer?.types ?? []).includes('Files')
    }

    function onDragEnter(e: DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth += 1
      setDragActive(true)
    }
    function onDragOver(e: DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault() // required to allow a drop at all
    }
    function onDragLeave(e: DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth = Math.max(0, dragDepth - 1)
      if (dragDepth === 0) setDragActive(false)
    }
    function onDrop(e: DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragDepth = 0
      setDragActive(false)
      const files = Array.from(e.dataTransfer?.files ?? [])
      if (files.length > 0) void handleFilesRef.current(files)
    }

    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
  }, [])

  function openPicker() {
    fileInputRef.current?.click()
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = '' // let the same file be re-picked later
    if (files.length > 0) void handleFiles(files)
  }

  function setGrounding(mode: ComposerGroundingMode) {
    onGroundingChange(mode)
    persistGrounding(mode)
  }

  return (
    <div className="composer">
      {dragActive && (
        <div className="drawer-backdrop drop-overlay" aria-hidden="true">
          <div className="drop-overlay-card">Drop files to add them to your corpus</div>
        </div>
      )}

      <div className="composer-inner">
        <div className="composer-pills">
          <ModeToggle value={mode} onChange={setMode} />
          <GroundingToggle value={grounding} onChange={setGrounding} disabled={mode === 'find'} />
        </div>
        <div className="row">
          <button
            type="button"
            className="attach-btn"
            onClick={openPicker}
            aria-label="Attach files"
            title="Attach files"
          >
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
          <input ref={fileInputRef} type="file" multiple hidden onChange={onPick} />
          <input
            type="text"
            value={input}
            placeholder={mode === 'find' ? 'Find in your documents…' : 'Ask a question…'}
            disabled={busy || finding}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend()
            }}
          />
          <button
            type="button"
            className="btn-primary"
            onClick={handleSend}
            disabled={busy || finding || !input.trim()}
          >
            {finding ? 'Finding…' : busy ? 'Thinking…' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

/** One citation as returned by ``GET /search`` (mirrors api.schemas.Source). */
type Source = {
  path: string
  page: number
  score: number
  snippet: string
  index?: number | null
}

/** Response body of ``GET /search`` (mirrors api.schemas.SearchResponse). */
type SearchResponse = {
  summary: string
  sources: Source[]
}

/**
 * Output mode — a UI-only choice (the engine only ever sees the per-request ``recap`` flag):
 *  - human   → recap=true  → a conversational AI answer + readable source cards.
 *  - machine → recap=false → the raw reranker results as JSON (no LLM), for tools/integrations.
 */
type Mode = 'human' | 'machine'

/** Just the file name, so long ingest paths don't blow out the citation. */
function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

/** Person silhouette — the Human-mode glyph carried in the toggle thumb. */
function HumanGlyph() {
  return (
    <svg className="mode-glyph" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="5.2" r="2.8" />
      <path d="M2.6 13.8c0-3 2.4-4.8 5.4-4.8s5.4 1.8 5.4 4.8z" />
    </svg>
  )
}

/** Robot head — the Machine-mode glyph carried in the toggle thumb. */
function RobotGlyph() {
  return (
    <svg className="mode-glyph" viewBox="0 0 16 16" aria-hidden="true">
      <line x1="8" y1="1.4" x2="8" y2="4.2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="8" cy="1.4" r="1.1" />
      <rect x="3" y="4.4" width="10" height="8.2" rx="2.6" />
      <circle cx="6" cy="8.3" r="1.15" fill="#fff" />
      <circle cx="10" cy="8.3" r="1.15" fill="#fff" />
      <rect x="6.3" y="10.7" width="3.4" height="1" rx="0.5" fill="#fff" />
    </svg>
  )
}

/**
 * Search panel with two output modes (the choice lives entirely here in the UI):
 *  - Human   → conversational AI recap (markdown) + readable source cards.
 *  - Machine → the raw reranker results as JSON, no LLM, for piping into external tools.
 * Both modes just flip the engine's existing per-request ``recap`` flag — the core is untouched.
 */
export default function Search({ token }: { token: string }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [mode, setMode] = useState<Mode>(() =>
    localStorage.getItem('searchMode') === 'machine' ? 'machine' : 'human',
  )

  function toggleMode() {
    setMode((m) => {
      const next: Mode = m === 'human' ? 'machine' : 'human'
      localStorage.setItem('searchMode', next)
      return next
    })
  }

  async function runSearch() {
    setError(null)
    setResult(null)
    setCopied(false)
    setLoading(true)
    try {
      // Human asks for the AI recap; Machine skips it (recap=false → no LLM, raw results only).
      const recap = mode === 'human'
      const resp = await fetch(`/search?q=${encodeURIComponent(query)}&recap=${recap}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) {
        throw new Error(`Search failed: ${resp.status} ${resp.statusText}`)
      }
      const data = (await resp.json()) as SearchResponse
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  function copyJson() {
    if (!result) return
    void navigator.clipboard.writeText(JSON.stringify(result, null, 2)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const hasSources = result != null && result.sources.length > 0
  const modeHint =
    mode === 'human'
      ? 'Conversational AI answer synthesised from the best passages, with its source.'
      : 'Raw reranker results as JSON — no LLM call. For tools & integrations.'

  return (
    <section className="panel search">
      <h2>Search</h2>
      <div className="row">
        <input
          type="text"
          value={query}
          placeholder="Ask a question…"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') runSearch()
          }}
        />
        <button type="button" onClick={runSearch} disabled={loading || !query}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      <label
        className="switch mode-switch"
        data-mode={mode}
        title="Human = conversational AI answer · Machine = raw JSON results for tools"
      >
        <input
          type="checkbox"
          role="switch"
          checked={mode === 'machine'}
          onChange={toggleMode}
          aria-label={`Output mode: ${mode}`}
        />
        <span className="switch-track" aria-hidden="true">
          <span className="switch-thumb">{mode === 'human' ? <HumanGlyph /> : <RobotGlyph />}</span>
        </span>
        <span
          className="mode-info"
          role="img"
          aria-label={modeHint}
          title={modeHint}
          onClick={(e) => e.preventDefault()}
        >
          ⓘ
        </span>
        <span className="switch-label">{mode === 'human' ? 'Human' : 'Machine'}</span>
      </label>

      {error && <p className="error">{error}</p>}

      {loading && (
        <div className="skeleton" aria-hidden="true">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      )}

      {!loading && result && (
        <div className="result">
          {!hasSources ? (
            <p className="empty">No matching passage found. Try rephrasing, or ingest more files.</p>
          ) : mode === 'machine' ? (
            <div className="machine">
              <div className="json-head">
                <span className="sources-label">Raw JSON · GET /search?recap=false</span>
                <button type="button" className="copy-btn" onClick={copyJson}>
                  {copied ? 'Copied ✓' : 'Copy'}
                </button>
              </div>
              <pre className="json">
                <code>{JSON.stringify(result, null, 2)}</code>
              </pre>
            </div>
          ) : (
            <>
              {result.summary && (
                <div className="recap">
                  <ReactMarkdown>{result.summary}</ReactMarkdown>
                </div>
              )}
              <div className="sources">
                <span className="sources-label">Source</span>
                {result.sources.map((s, i) => (
                  <div className="source" key={i}>
                    <div className="source-head">
                      <span className="source-path" title={s.path}>
                        {fileName(s.path)}
                      </span>
                      <span className="badge badge-page">p. {s.page}</span>
                      <span className="badge badge-score">{(s.score * 100).toFixed(0)}% match</span>
                      {s.index != null && (
                        <span className="badge badge-passage">passage #{s.index}</span>
                      )}
                    </div>
                    {s.snippet && <blockquote className="snippet">“{s.snippet}”</blockquote>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  )
}

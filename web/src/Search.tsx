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

/** Just the file name, so long ingest paths don't blow out the citation. */
function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

/**
 * Search panel: type a question, GET /search?q=… with the shared bearer token,
 * then render the recap (markdown) plus the best source — its page, relevance,
 * and the matched passage so you can see *where* in the document it came from.
 */
export default function Search({ token }: { token: string }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [recapEnabled, setRecapEnabled] = useState(() => {
    const saved = localStorage.getItem('recapEnabled')
    return saved === null ? true : saved === 'true'
  })

  function toggleRecap() {
    setRecapEnabled((on) => {
      const next = !on
      localStorage.setItem('recapEnabled', String(next))
      return next
    })
  }

  async function runSearch() {
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const resp = await fetch(`/search?q=${encodeURIComponent(query)}&recap=${recapEnabled}`, {
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

  const hasSources = result != null && result.sources.length > 0

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

      <label className="switch" title="Generate an AI summary of the best passage">
        <input type="checkbox" checked={recapEnabled} onChange={toggleRecap} />
        <span className="switch-track" aria-hidden="true">
          <span className="switch-thumb" />
        </span>
        <span className="switch-label">AI recap</span>
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
          {hasSources ? (
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
          ) : (
            <p className="empty">No matching passage found. Try rephrasing, or ingest more files.</p>
          )}
        </div>
      )}
    </section>
  )
}

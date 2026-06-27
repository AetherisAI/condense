import { useState } from 'react'

/** One citation as returned by ``GET /search`` (mirrors api.schemas.Source). */
type Source = {
  path: string
  page: number
  score: number
}

/** Response body of ``GET /search`` (mirrors api.schemas.SearchResponse). */
type SearchResponse = {
  summary: string
  sources: Source[]
}

/**
 * Search panel: type a query, GET /search?q=… with the shared bearer token,
 * then render the recap plus its source citations as `path:page (score)`.
 */
export default function Search({ token }: { token: string }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function runSearch() {
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const resp = await fetch(`/search?q=${encodeURIComponent(query)}`, {
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

  return (
    <section className="panel">
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
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="result">
          <p className="summary">{result.summary}</p>
          <ul>
            {result.sources.map((s, i) => (
              <li key={i}>
                {s.path}:{s.page} ({s.score.toFixed(3)})
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

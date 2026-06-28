import { useState } from 'react'

/** Per-file outcome from ``POST /ingest`` (mirrors api.schemas.IngestFileResult). */
type IngestFileResult = {
  path: string
  status: string
  content_hash?: string | null
  chunks?: number | null
  detail?: string | null
}

/** Response body of ``POST /ingest`` (mirrors api.schemas.IngestResponse). */
type IngestResponse = {
  tenant: string
  results: IngestFileResult[]
}

/**
 * Ingest panel: pick one or more files, POST them as multipart/form-data under
 * the field name "files" with the bearer token, then list each path + status.
 * The browser sets the multipart boundary, so we never set Content-Type manually.
 */
export default function Ingest({ token }: { token: string }) {
  const [files, setFiles] = useState<FileList | null>(null)
  const [results, setResults] = useState<IngestFileResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function runIngest() {
    if (!files || files.length === 0) return
    setError(null)
    setResults(null)
    setLoading(true)
    try {
      const form = new FormData()
      for (const file of Array.from(files)) {
        form.append('files', file)
      }
      const resp = await fetch('/ingest', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      })
      if (!resp.ok) {
        throw new Error(`Ingest failed: ${resp.status} ${resp.statusText}`)
      }
      const data = (await resp.json()) as IngestResponse
      setResults(data.results)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="panel">
      <h2>Ingest</h2>
      <div className="row">
        <input
          type="file"
          multiple
          onChange={(e) => setFiles(e.target.files)}
        />
        <button
          type="button"
          onClick={runIngest}
          disabled={loading || !files || files.length === 0}
        >
          {loading ? 'Uploading…' : 'Ingest'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {results && (
        <ul className="ingest-results">
          {results.map((r, i) => (
            <li key={i}>
              {r.path} — <span className={`status status-${r.status}`}>{r.status}</span>
              {r.chunks != null ? ` (${r.chunks} chunks)` : ''}
              {r.detail ? ` — ${r.detail}` : ''}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

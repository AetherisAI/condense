import { apiFetch } from './api'

/** Per-file outcome from ``POST /ingest`` (mirrors api.schemas.IngestFileResult). Shared by every
 * upload surface (`Composer.tsx`'s in-chat ingest, `Ingest.tsx`'s standalone panel) so the wire
 * shape and the multipart request itself are defined exactly once. */
export type IngestFileResult = {
  path: string
  status: string
  content_hash?: string | null
  chunks?: number | null
  detail?: string | null
}

/** Response body of ``POST /ingest`` (mirrors api.schemas.IngestResponse). */
export type IngestResponse = {
  tenant: string
  results: IngestFileResult[]
}

/**
 * Upload `files` to `POST /ingest` as multipart/form-data — the browser sets the multipart
 * boundary, so `Content-Type` is never set by hand. Carries each file's true last-modified time
 * as the `modified_at` form field, a JSON `{upload_name: iso8601}` map built from the browser's
 * own `File.lastModified` — the same shape/purpose as the folder agent's own `modified_at` map
 * (`agent/client.py`), so a browser-uploaded copy can win version-collapse against a stale
 * indexed one exactly the way an agent-uploaded copy already does (D44).
 *
 * Throws on a non-OK response (or a network failure) — callers decide how to surface that per
 * file; this helper only ever makes the one request for the whole batch, mirroring the server's
 * own one-call-per-batch contract.
 */
export async function postIngest(token: string, files: File[]): Promise<IngestResponse> {
  const form = new FormData()
  const mtimes: Record<string, string> = {}
  for (const file of files) {
    form.append('files', file)
    mtimes[file.name] = new Date(file.lastModified).toISOString()
  }
  form.append('modified_at', JSON.stringify(mtimes))
  const resp = await apiFetch('/ingest', token, { method: 'POST', body: form })
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}`)
  }
  return (await resp.json()) as IngestResponse
}

/** Short, human file size (e.g. the queued list shows it under the name). */
export function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

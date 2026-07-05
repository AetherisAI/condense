import { apiFetch } from './api'

/** One ingested document (mirrors api.schemas.DocumentSummary). Shared by `Library.tsx` (the
 * full listing) and `Chat.tsx` (the empty-corpus nudge check, D57/Task U6) so both agree on one
 * fetch + shape instead of two copies drifting apart. */
export type DocumentSummary = {
  path: string
  source_hash: string
  chunks: number
  // D44: the source file's true last-modified time (or indexed_at fallback) — additive,
  // not yet rendered anywhere.
  modified_at?: string | null
  indexed_at?: string | null
}

/** Response body of ``GET /documents`` (mirrors api.schemas.DocumentsResponse). */
export type DocumentsResponse = {
  tenant: string
  documents: DocumentSummary[]
  supported: boolean
}

/** ``GET /documents`` — throws on a non-2xx response, the same contract every call site already
 * expected of its own inlined fetch before this was extracted. */
export async function fetchDocuments(token: string): Promise<DocumentsResponse> {
  const resp = await apiFetch('/documents', token)
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`)
  return (await resp.json()) as DocumentsResponse
}

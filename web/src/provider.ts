/**
 * Pure-frontend guess at which LLM provider an API key belongs to, from its shape alone (D57/Task
 * U6) — this NEVER validates the key or calls out anywhere; it only drives a live hint next to
 * the "LLM API key" preview field in the System drawer's Model section as the user types. Order
 * matters: the more specific `sk-ant-` prefix is checked before the general `sk-` prefix, since
 * every Anthropic key would otherwise also match "starts with sk-".
 */

export type DetectedProvider = 'Anthropic' | 'OpenAI' | 'Mistral (likely)'

/** 25-40 char single alnum token (no dashes/underscores) — Mistral's key shape, checked only
 * once the `sk-`-prefixed providers above have been ruled out. */
const MISTRAL_SHAPE = /^[A-Za-z0-9]{25,40}$/

export function detectProvider(key: string): DetectedProvider | null {
  const trimmed = key.trim()
  if (!trimmed) return null
  if (trimmed.startsWith('sk-ant-')) return 'Anthropic'
  if (trimmed.startsWith('sk-')) return 'OpenAI'
  if (MISTRAL_SHAPE.test(trimmed)) return 'Mistral (likely)'
  return null
}

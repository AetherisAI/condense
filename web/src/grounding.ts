/**
 * The composer's own grounding toggle (D46/D57 Task U2) — a small, component-free module (kept
 * separate from `Composer.tsx` so that file only ever exports components, which is what keeps
 * React Fast Refresh working; see `react/only-export-components`).
 *
 * `ComposerGroundingMode` ("strict"|"open") is UI-only: the wire/persisted grounding type a turn
 * can carry (`Chat.tsx`'s own `GroundingMode`) still includes "hybrid" for other consumers and
 * for conversations that already recorded it — this toggle just never offers it as a choice
 * going forward, and `loadStoredGrounding` migrates anyone's remembered "hybrid" preference to
 * "open" (the bucket the API always treated it closest to for a corpus-first assistant).
 */

export type ComposerGroundingMode = 'strict' | 'open'

const GROUNDING_STORAGE_KEY = 'chatGrounding'

function isComposerGroundingMode(value: string | null): value is ComposerGroundingMode {
  return value === 'strict' || value === 'open'
}

/** Reads the persisted grounding toggle, migrating a stored "hybrid" (the now-retired middle UI
 * option) to "open" on load. Only the toggle's own remembered preference is migrated;
 * already-persisted CONVERSATIONS that recorded "hybrid" on a turn are untouched (`Chat.tsx`'s
 * `turnsFromDetail` reads each turn's own stored grounding, never this). */
export function loadStoredGrounding(): ComposerGroundingMode {
  const stored = localStorage.getItem(GROUNDING_STORAGE_KEY)
  if (stored === 'hybrid') {
    localStorage.setItem(GROUNDING_STORAGE_KEY, 'open')
    return 'open'
  }
  return isComposerGroundingMode(stored) ? stored : 'strict'
}

/** Persists the chosen grounding mode (mirrors `loadStoredGrounding`'s storage key). */
export function persistGrounding(mode: ComposerGroundingMode): void {
  localStorage.setItem(GROUNDING_STORAGE_KEY, mode)
}

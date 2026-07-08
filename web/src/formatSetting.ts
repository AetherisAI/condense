/** Render a raw settings value (from `/status`'s `settings` map) as display text. Shared between
 * `SystemMenu.tsx` and `SettingRow.tsx` so both format `null`/booleans/numbers identically. */
export function fmtSetting(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  return String(v)
}

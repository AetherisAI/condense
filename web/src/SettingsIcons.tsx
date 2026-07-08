/** Small inline-SVG icons for the System drawer's settings rows — same hand-drawn, 16x16-viewBox,
 * currentColor-stroke style already used by `AccessTokens.tsx`'s `TrashIcon` (no icon-font/library
 * dependency, matches the app's existing convention). */

/** A restart-required indicator — a circular arrow, used both in the top summary banner and as
 * the small inline chip on a setting's label line. */
export function RestartIcon() {
  return (
    <svg viewBox="0 0 16 16" width="9" height="9" aria-hidden="true">
      <path
        d="M3 8a5 5 0 1 1 1.6 3.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path d="M3 5.2V8h2.8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/** Copy-to-clipboard glyph for a truncated settings value — smaller sibling of `AccessTokens.tsx`'s
 * text `.copy-btn`, sized for an inline icon-only button next to a one-line value. */
export function CopyIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <rect x="5.5" y="5.5" width="8" height="8" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M3.5 10.2V3.8a1 1 0 0 1 1-1h6.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** Small checkmark used to flip a just-copied button into a confirmation state. */
export function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <path
        d="M3.5 8.5l3 3 6-7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
